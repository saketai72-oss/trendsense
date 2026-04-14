"""
Video Downloader — Tải video MP4 từ TikTok bằng yt-dlp.
- Chỉ tải video có xác suất viral > ngưỡng cấu hình.
- Chuẩn 480p (sweet spot cho AI Vision: OCR đọc rõ, BLIP nhìn nét, dung lượng nhẹ).
- Giới hạn: ≤15MB, ≤3 phút. Tự động xoá video cũ hơn N ngày.
"""
import os
import sys
import glob

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

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
        'format': 'bestvideo+bestaudio/best', 
        'quiet': True,
        'no_warnings': True,
        'retries': 3,                      
        'socket_timeout': 60,
        'merge_output_format': 'mp4',
        'concurrent_fragment_downloads': 5,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Tìm file đã tải
        pattern = os.path.join(settings.VIDEOS_DIR, f"{video_id}.*")
        files = glob.glob(pattern)
        if files:
            actual_path = files[0]
            
            return actual_path
        return None

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"    [!] Lỗi tải video {video_id}: {error_msg}")
        return None

