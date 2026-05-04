"""
Script sửa chữa: Tìm và khắc phục video có sentiment 'KHÔNG CÓ BÌNH LUẬN'.

2 chế độ:
1. Chế độ xem (mặc định): Liệt kê tất cả video bị ảnh hưởng.
2. Chế độ sửa (--fix): Reset ai_status về 'pending' và xóa sentiment sai.

Sau đó chạy lại AI pipeline: python -m services.ai_engine.ai_core_main

Chạy:
    python scripts/fix_sentiment_mismatch.py           # Xem danh sách
    python scripts/fix_sentiment_mismatch.py --fix      # Reset để phân tích lại
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.session import get_connection


def find_no_comment_videos():
    """Tìm tất cả video có sentiment = KHÔNG CÓ BÌNH LUẬN."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT video_id, caption, comments,
                       CASE WHEN top1_cmt IS NOT NULL AND top1_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top2_cmt IS NOT NULL AND top2_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top3_cmt IS NOT NULL AND top3_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top4_cmt IS NOT NULL AND top4_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top5_cmt IS NOT NULL AND top5_cmt != '' THEN 1 ELSE 0 END AS db_comment_count
                FROM videos
                WHERE video_sentiment = '⚪ KHÔNG CÓ BÌNH LUẬN'
                ORDER BY comments DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()


def reset_no_comment_videos():
    """Reset ai_status về 'pending' cho video bị ảnh hưởng."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE videos
                SET ai_status = 'pending',
                    video_sentiment = NULL
                WHERE video_sentiment = '⚪ KHÔNG CÓ BÌNH LUẬN'
            """)
            updated = cursor.rowcount
            conn.commit()
            return updated
    except Exception as e:
        conn.rollback()
        print(f"[❌] Lỗi: {e}")
        return 0
    finally:
        conn.close()


def main():
    fix_mode = '--fix' in sys.argv

    print("🔍 Đang tìm video có sentiment 'KHÔNG CÓ BÌNH LUẬN'...")
    print("=" * 70)

    affected = find_no_comment_videos()

    if not affected:
        print("✅ Không tìm thấy video nào có sentiment 'KHÔNG CÓ BÌNH LUẬN'.")
        return

    print(f"📋 Tìm thấy {len(affected)} video:\n")
    print(f"  {'Video ID':<22} {'💬 TikTok':>10} {'💾 DB':>8}  {'Caption (rút gọn)'}")
    print(f"  {'-'*22} {'-'*10} {'-'*8}  {'-'*30}")

    has_comments_on_tiktok = 0
    for row in affected:
        vid, caption, tiktok_comments, db_comments = row
        caption_short = (caption[:35] + '...') if caption and len(caption) > 35 else (caption or '')
        marker = ' ⚠️' if tiktok_comments and tiktok_comments > 0 else ''
        if tiktok_comments and tiktok_comments > 0:
            has_comments_on_tiktok += 1
        print(f"  {vid:<22} {tiktok_comments or 0:>10,} {db_comments:>8}{marker}  {caption_short}")

    print(f"\n{'=' * 70}")
    print(f"📊 Tổng: {len(affected)} video | ⚠️ {has_comments_on_tiktok} video có comments trên TikTok nhưng rỗng trong DB")

    if not fix_mode:
        print(f"\n💡 Chạy với --fix để reset ai_status về 'pending':")
        print(f"   python scripts/fix_sentiment_mismatch.py --fix")
        return

    # Chế độ fix
    print(f"\n🔧 Đang reset ai_status về 'pending'...")
    updated = reset_no_comment_videos()
    print(f"✅ Đã reset {updated} video.")

    if has_comments_on_tiktok > 0:
        print(f"\n⚠️  {has_comments_on_tiktok} video có comments trên TikTok nhưng DB rỗng.")
        print(f"   Cần re-scrape comments để phân tích sentiment đúng:")
        print(f"   python scripts/rescrape_comments.py")

    print(f"\n👉 Chạy lại AI pipeline:")
    print(f"   python -m services.ai_engine.ai_core_main")


if __name__ == "__main__":
    main()
