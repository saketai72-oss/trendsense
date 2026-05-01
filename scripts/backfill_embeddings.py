"""
Backfill Embeddings — Điền vector embedding cho video đã phân tích nhưng chưa có embedding.
=========================================================================================
Chạy LOCAL để tránh phát sinh chi phí trên Render/Modal.

Yêu cầu:
  - GEMINI_API_KEY trong .env (free tier: 1500 requests/ngày cho text-embedding-004)
  - DATABASE_URL trong .env

Sử dụng:
  python scripts/backfill_embeddings.py              # Chạy tất cả video thiếu embedding
  python scripts/backfill_embeddings.py --recent     # Chỉ video dưới 14 ngày
  python scripts/backfill_embeddings.py --limit 50   # Giới hạn 50 video
  python scripts/backfill_embeddings.py --dry-run    # Chỉ xem có bao nhiêu video, không gọi API
  python scripts/backfill_embeddings.py --recent --limit 50 --dry-run
"""
import os
import sys
import argparse
import time

# Thêm đường dẫn gốc để import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from core.db.session import get_connection


def get_videos_needing_embeddings(limit=None, recent=False):
    """Lấy video có ai_status='completed' nhưng embedding IS NULL.
    recent=True: chỉ lấy video còn trong chu kỳ dự báo (viral_probability > 0).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT video_id, audio_transcript, video_description
                FROM videos
                WHERE ai_status = 'completed'
                  AND embedding IS NULL
            """
            if recent:
                sql += " AND viral_probability > 0"
            sql += " ORDER BY scrape_date DESC"
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            rows = cur.fetchall()
            return [
                {"video_id": r[0], "audio_transcript": r[1] or "", "video_description": r[2] or ""}
                for r in rows
            ]
    finally:
        conn.close()


def count_missing(recent=False):
    """Đếm video thiếu embedding."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT COUNT(*) FROM videos
                WHERE ai_status = 'completed' AND embedding IS NULL
            """
            if recent:
                sql += " AND viral_probability > 0"
            cur.execute(sql)
            return cur.fetchone()[0]
    finally:
        conn.close()


def count_total_completed():
    """Đếm tổng video completed."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM videos WHERE ai_status = 'completed'")
            return cur.fetchone()[0]
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill embedding cho video thiếu")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số video xử lý")
    parser.add_argument("--recent", action="store_true", help="Chỉ video còn trong chu kỳ dự báo (viral_probability > 0)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ xem số lượng, không gọi API")
    parser.add_argument("--delay", type=float, default=1.0, help="Giây nghỉ giữa mỗi request (mặc định 1.0s)")
    args = parser.parse_args()

    # Kiểm tra GEMINI_API_KEY
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key and not args.dry_run:
        print("❌ GEMINI_API_KEY không tìm thấy trong .env")
        print("   Thêm GEMINI_API_KEY=xxx vào file .env rồi thử lại.")
        sys.exit(1)

    total_completed = count_total_completed()
    missing = count_missing(recent=args.recent)
    has_embedding = total_completed - count_missing(recent=False)

    print("=" * 55)
    print("📊 TÌNH TRẠNG EMBEDDING")
    if args.recent:
        print("   (Chỉ video còn dự báo — viral_probability > 0)")
    print("=" * 55)
    print(f"   Video completed:       {total_completed}")
    print(f"   Đã có embedding:       {has_embedding}")
    print(f"   Thiếu embedding:       {missing}")
    print("=" * 55)

    if missing == 0:
        print("✅ Tất cả video completed đều đã có embedding!")
        return

    if args.dry_run:
        scope = "video còn dự báo (viral_probability > 0)" if args.recent else "tất cả video"
        print(f"\n🔍 Dry run: Có {missing} video cần backfill ({scope}).")
        if args.limit:
            print(f"   Với --limit {args.limit}, sẽ xử lý {min(args.limit, missing)} video.")
        print(f"   Ước tính thời gian: ~{min(args.limit or missing, missing) * args.delay:.0f}s")
        return

    # Lấy danh sách video cần xử lý
    videos = get_videos_needing_embeddings(limit=args.limit, recent=args.recent)
    total = len(videos)
    print(f"\n🚀 Bắt đầu backfill {total} video (delay {args.delay}s/request)...\n")

    # Import embedding service
    from backend.api.embedding_service import update_video_embedding

    success = 0
    failed = 0
    skipped = 0

    for i, video in enumerate(videos, 1):
        vid = video["video_id"]
        transcript = video["audio_transcript"]
        description = video["video_description"]

        # Bỏ qua video không có transcript VÀ không có description
        if not transcript.strip() and not description.strip():
            print(f"  [{i}/{total}] ⏭️  {vid} — không có text, bỏ qua")
            skipped += 1
            continue

        print(f"  [{i}/{total}] 🔄 {vid}...", end=" ", flush=True)

        try:
            ok = update_video_embedding(vid, transcript, description)
            if ok:
                print("✅")
                success += 1
            else:
                print("⚠️ skipped (API trả None)")
                skipped += 1
        except Exception as e:
            print(f"❌ {e}")
            failed += 1

        # Rate limit: nghỉ giữa mỗi request
        if i < total:
            time.sleep(args.delay)

    print("\n" + "=" * 55)
    print("📊 KẾT QUẢ BACKFILL")
    print("=" * 55)
    print(f"   Thành công:  {success}")
    print(f"   Bỏ qua:      {skipped}")
    print(f"   Lỗi:         {failed}")
    print(f"   Tổng xử lý:  {total}")
    print("=" * 55)


if __name__ == "__main__":
    main()
