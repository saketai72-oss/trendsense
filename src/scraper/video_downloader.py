"""
Video Downloader — Tải video MP4 từ TikTok bằng yt-dlp.
Chỉ tải video có xác suất viral > ngưỡng cấu hình.
Tự động dọn dẹp video cũ hơn N ngày.
"""
import os
import sys
import glob
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
from database import (
    get_viral_videos_for_download, update_video_path,
    get_videos_with_expired_files, clear_video_path
)


def download_video(video_url, video_id):
    """
    Tải 1 video bằng yt-dlp, trả về đường dẫn file hoặc None nếu lỗi.
    yt-dlp tự xuyên qua lớp bảo vệ của TikTok và tải MP4 không logo.
    """
    import yt_dlp

    output_path = os.path.join(settings.VIDEOS_DIR, f"{video_id}.mp4")

    # Skip nếu file đã tồn tại (chống tải trùng)
    if os.path.exists(output_path):
        return output_path

    ydl_opts = {
        'outtmpl': os.path.join(settings.VIDEOS_DIR, f'{video_id}.%(ext)s'),
        'format': 'mp4/best',         # Ưu tiên MP4
        'quiet': True,
        'no_warnings': True,
        'retries': 2,                  # Retry 2 lần nếu lỗi mạng
        'socket_timeout': 30,
        'merge_output_format': 'mp4',  # Force output MP4
        'concurrent_fragment_downloads': 3,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Tìm file đã tải (có thể ext khác mp4 ban đầu)
        pattern = os.path.join(settings.VIDEOS_DIR, f"{video_id}.*")
        files = glob.glob(pattern)
        if files:
            actual_path = files[0]
            return actual_path
        return None

    except Exception as e:
        print(f"    [!] Lỗi tải video {video_id}: {str(e)[:80]}")
        return None


def download_viral_videos():
    """
    Tải tất cả video viral chưa có file MP4.
    Chỉ chạy khi DOWNLOAD_VIDEOS = True trong settings.
    """
    if not settings.DOWNLOAD_VIDEOS:
        print("[*] Tải video đã TẮT trong settings.")
        return

    threshold = settings.VIRAL_DOWNLOAD_THRESHOLD
    videos = get_viral_videos_for_download(threshold)

    if not videos:
        print(f"[*] Không có video viral mới (>{threshold}%) cần tải.")
        return

    print(f"\n📥 BẮT ĐẦU TẢI {len(videos)} VIDEO VIRAL (>{threshold}%)")
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

    print(f"\n[✓] Đã tải xong: {success}/{len(videos)} video.")


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
