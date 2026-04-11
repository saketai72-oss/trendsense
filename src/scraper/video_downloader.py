"""
Video Downloader — Tải video MP4 từ TikTok bằng yt-dlp.
- Chỉ tải video có xác suất viral > ngưỡng cấu hình.
- Chuẩn 480p (sweet spot cho AI Vision: OCR đọc rõ, BLIP nhìn nét, dung lượng nhẹ).
- Giới hạn: ≤15MB, ≤3 phút. Tự động xoá video cũ hơn N ngày.
"""
import os
import sys
import glob
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

from src.scraper.database import (
    get_viral_videos_for_download, get_all_videos_for_download, update_video_path,
    get_videos_with_expired_files, clear_video_path,
    get_videos_with_khac_category, mark_video_download_failed
)


def download_video(video_url, video_id):
    """
    Tải 1 video bằng yt-dlp, trả về đường dẫn file hoặc None nếu lỗi.
    - Chuẩn 480p (sweet spot: nét đủ cho OCR/BLIP, nhẹ ~5-8MB/phút)
    - Bỏ qua video > MAX_VIDEO_DURATION giây
    - Tự xoá nếu file > MAX_VIDEO_SIZE_MB
    """
    import yt_dlp

    output_path = os.path.join(settings.VIDEOS_DIR, f"{video_id}.mp4")

    # Skip nếu file đã tồn tại (chống tải trùng)
    if os.path.exists(output_path):
        return output_path

    ydl_opts = {
        'outtmpl': os.path.join(settings.VIDEOS_DIR, f'{video_id}.%(ext)s'),
        'format': settings.VIDEO_FORMAT,   # 480p — sweet spot cho AI Vision
        'quiet': True,
        'no_warnings': True,
        'retries': 2,                      # Retry 2 lần nếu lỗi mạng
        'socket_timeout': 30,
        'merge_output_format': 'mp4',      # Force output MP4
        'concurrent_fragment_downloads': 3,
        # Bỏ qua video dài hơn MAX_VIDEO_DURATION giây
        'match_filter': yt_dlp.utils.match_filter_func(
            f"duration < {settings.MAX_VIDEO_DURATION}"
        ),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Tìm file đã tải (có thể ext khác mp4 ban đầu)
        pattern = os.path.join(settings.VIDEOS_DIR, f"{video_id}.*")
        files = glob.glob(pattern)
        if files:
            actual_path = files[0]

            # Kiểm tra dung lượng — xoá nếu quá nặng
            size_mb = os.path.getsize(actual_path) / (1024 * 1024)
            if size_mb > settings.MAX_VIDEO_SIZE_MB:
                print(f"    [!] Video quá nặng ({size_mb:.1f}MB > {settings.MAX_VIDEO_SIZE_MB}MB), xoá.")
                os.remove(actual_path)
                return None

            return actual_path
        return None

    except Exception as e:
        error_msg = str(e)[:80]
        # Nếu bị filter do duration → thông báo rõ
        if "Rejected" in error_msg or "match_filter" in error_msg:
            print(f"    [!] Video {video_id}: Thời lượng vượt {settings.MAX_VIDEO_DURATION}s, bỏ qua.")
        else:
            print(f"    [!] Lỗi tải video {video_id}: {error_msg}")
        return None


def download_viral_videos():
    """
    Tải tất cả video viral chưa có file MP4.
    Chỉ chạy khi DOWNLOAD_VIDEOS = True trong settings.
    """
    if not settings.DOWNLOAD_VIDEOS:
        print("[*] Tải video đã TẮT trong settings.")
        return

    if getattr(settings, 'DOWNLOAD_VIRAL_ONLY', True):
        threshold = settings.VIRAL_DOWNLOAD_THRESHOLD
        videos = get_viral_videos_for_download(threshold)
        if not videos:
            print(f"[*] Không có video viral mới (>{threshold}%) cần tải.")
            return
        print(f"\n📥 BẮT ĐẦU TẢI {len(videos)} VIDEO VIRAL (>{threshold}%) — Chuẩn 480p")
    else:
        videos = get_all_videos_for_download()
        if not videos:
            print(f"[*] Không có video mới nào cần tải.")
            return
        print(f"\n📥 BẮT ĐẦU TẢI {len(videos)} VIDEO (Bỏ qua viral threshold) — Chuẩn 480p")

    print("=" * 50)

    success = 0
    for i, video in enumerate(videos, 1):
        vid = video['video_id']
        url = video['link']
        print(f"  [{i}/{len(videos)}] Đang tải: {vid}...", end=" ")

        file_path = download_video(url, vid)
        if file_path:
            update_video_path(vid, file_path)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"✅ ({size_mb:.1f} MB)")
            success += 1
        else:
            print("❌ Thất bại")
            mark_video_download_failed(vid)

    print(f"\n[✓] Đã tải xong: {success}/{len(videos)} video.")


def download_for_khac_category():
    """
    Tải video cho các video có danh mục "🌍 Khác" nhưng chưa có file MP4.
    Mục đích: cung cấp file cho Vision AI + Ollama phân loại lại.
    """
    if not settings.DOWNLOAD_VIDEOS:
        return []

    khac_videos = get_videos_with_khac_category()
    # Lọc ra video chưa có file MP4
    need_download = [v for v in khac_videos if not v.get('video_path') or not os.path.exists(str(v.get('video_path', '')))]

    if not need_download:
        return khac_videos  # Tất cả đã có MP4

    print(f"\n📥 TẢI {len(need_download)} VIDEO 'Khác' ĐỂ AI PHÂN LOẠI LẠI — Chuẩn 480p")
    print("=" * 50)

    success = 0
    for i, video in enumerate(need_download, 1):
        vid = video['video_id']
        url = video['link']
        print(f"  [{i}/{len(need_download)}] Tải video Khác: {vid}...", end=" ")

        file_path = download_video(url, vid)
        if file_path:
            update_video_path(vid, file_path)
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"✅ ({size_mb:.1f} MB)")
            video['video_path'] = file_path  # Cập nhật trong dict
            success += 1
        else:
            print("❌ Thất bại")

    print(f"[✓] Đã tải: {success}/{len(need_download)} video Khác.")

    # Trả về danh sách đầy đủ (bao gồm cả video đã có MP4 từ trước)
    return get_videos_with_khac_category()


def cleanup_old_videos():
    """
    Tự động xoá file MP4 cũ hơn VIDEO_RETENTION_DAYS ngày.
    Giải phóng dung lượng ổ cứng và giữ hệ thống gọn gàng.
    """
    days = settings.VIDEO_RETENTION_DAYS
    expired = get_videos_with_expired_files(days)

    if not expired:
        print(f"[*] 🧹 Không có video cũ hơn {days} ngày cần dọn.")
        return

    print(f"\n🧹 DỌN DẸP: Xoá {len(expired)} video cũ hơn {days} ngày")
    deleted = 0
    freed_mb = 0

    for video in expired:
        path = video['video_path']
        vid = video['video_id']

        if path and os.path.exists(path):
            try:
                size = os.path.getsize(path) / (1024 * 1024)
                os.remove(path)
                freed_mb += size
                deleted += 1
            except OSError as e:
                print(f"  [!] Không xoá được {path}: {e}")

        # Xoá reference trong DB dù file có tồn tại hay không
        clear_video_path(vid)

    print(f"[✓] Đã xoá {deleted} file, giải phóng {freed_mb:.1f} MB.")


if __name__ == "__main__":
    download_viral_videos()
    cleanup_old_videos()
