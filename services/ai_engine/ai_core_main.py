"""
AI Core Main — Orchestrator for the Hybrid AI Pipeline.
Modes:
1. Pending (Default): Process only new videos.
2. Re-scan: Reset all videos to 'pending' and re-run all AI analysis.
"""
import os
import sys
import argparse

# Thêm đường dẫn gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.db.models import get_pending_videos, reset_all_analysis_status
from services.ai_engine.processor import process_video_item

def run_ai_worker(reprocess_all=False):
    """
    Điều phối luồng xử lý AI.
    """
    if reprocess_all:
        print("\n[♻️] CHẾ ĐỘ RE-SCAN: Đang reset toàn bộ trạng thái phân tích...")
        reset_all_analysis_status()
        print("[✓] Đã reset xong. Bắt đầu phân tích lại từ đầu.\n")

    print("=" * 60)
    print("🧠 TRENDSENSE AI WORKER — BẮT ĐẦU")
    print("=" * 60)

    pending_videos = get_pending_videos()
    if not pending_videos:
        print("[✓] Không có video cần xử lý. Hệ thống đang nghỉ ngơi...")
        return

    total = len(pending_videos)
    print(f"[*] Tìm thấy {total} video đang chờ xử lý AI.")

    for i, video in enumerate(pending_videos, 1):
        vid = video['video_id']
        print(f"\n[{i}/{total}] Đang xử lý: {vid}")
        
        try:
            success = process_video_item(video)
            if success:
                print(f"    [✓] Hoàn thành Video {vid}")
        except Exception as e:
            print(f"    [❌] Lỗi nghiêm trọng khi xử lý video {vid}: {e}")

    print(f"\n✅ CÔNG VIỆC HOÀN THÀNH!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrendSense AI Core Orchestrator")
    parser.add_argument("--re-scan", action="store_true", help="Phân tích lại toàn bộ database từ đầu")
    
    args = parser.parse_args()
    
    # Chạy worker
    run_ai_worker(reprocess_all=args.re_scan)