"""
Script re-scrape bình luận cho video bị thiếu comments trong DB.

Tìm video có sentiment 'KHÔNG CÓ BÌNH LUẬN' nhưng có comments trên TikTok,
sử dụng Selenium để tải lại bình luận và cập nhật DB.

Sau khi chạy xong, chạy lại AI pipeline:
    python -m services.ai_engine.ai_core_main

Chạy:
    python scripts/rescrape_comments.py
"""
import os
import sys
import time
import random
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.session import get_connection
from core.db.models import update_rescraped_metadata
from services.tiktok_scraper.browser import init_driver
from services.tiktok_scraper.content_parser import extract_top_comments


def get_videos_needing_comments():
    """Lấy video có sentiment KHÔNG CÓ BÌNH LUẬN và có comments > 0 trên TikTok."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT video_id, link, caption, views, likes, comments, shares, saves,
                       create_time,
                       CASE WHEN top1_cmt IS NOT NULL AND top1_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top2_cmt IS NOT NULL AND top2_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top3_cmt IS NOT NULL AND top3_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top4_cmt IS NOT NULL AND top4_cmt != '' THEN 1 ELSE 0 END +
                       CASE WHEN top5_cmt IS NOT NULL AND top5_cmt != '' THEN 1 ELSE 0 END AS db_comment_count
                FROM videos
                WHERE video_sentiment = '⚪ KHÔNG CÓ BÌNH LUẬN'
                  AND comments > 0
                ORDER BY comments DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()


def main():
    print("🔄 RE-SCRAPE COMMENTS cho video bị thiếu bình luận")
    print("=" * 60)

    videos = get_videos_needing_comments()

    if not videos:
        print("✅ Không có video nào cần re-scrape comments.")
        print("   (Không tìm thấy video sentiment 'KHÔNG CÓ BÌNH LUẬN' có comments > 0)")
        return

    print(f"📋 Tìm thấy {len(videos)} video cần re-scrape comments:\n")
    for row in videos:
        vid, link, caption, views, likes, cmt_count, shares, saves, create_time, db_cmt = row
        caption_short = (caption[:40] + '...') if caption and len(caption) > 40 else (caption or '')
        print(f"   • {vid} — 💬{cmt_count:,} trên TikTok | 💾{db_cmt} trong DB | {caption_short}")

    print(f"\n{'=' * 60}")
    print("🚀 Đang khởi tạo trình duyệt...")

    driver = init_driver()
    updated = 0
    failed = 0

    try:
        for i, row in enumerate(videos, 1):
            vid, link, caption, views, likes, cmt_count, shares, saves, create_time, db_cmt = row

            print(f"\n[{i}/{len(videos)}] Đang xử lý: {vid}")
            print(f"  🔗 {link}")

            try:
                driver.get(link)
                time.sleep(random.uniform(3.0, 5.0))

                # Tải comments (has_comments=True vì TikTok báo có comments)
                top_comments = extract_top_comments(driver, has_comments_to_load=True)

                if not top_comments:
                    print(f"  [⚠️] Không tải được bình luận. Có thể bị chặn hoặc video đã bị xóa.")
                    failed += 1
                    continue

                print(f"  [✅] Tải được {len(top_comments)} bình luận:")
                for c in top_comments:
                    print(f"      💬 {c['text'][:60]}... (❤️{c['likes_num']:,})")

                # Chuẩn bị data để cập nhật DB
                data_dict = {
                    'caption': caption or '',
                    'views': views or 0,
                    'likes': likes or 0,
                    'comments': cmt_count or 0,
                    'shares': shares or 0,
                    'saves': saves or 0,
                    'create_time': create_time or 0,
                    'scrape_date': datetime.now().date().isoformat(),
                }

                for idx in range(5):
                    if idx < len(top_comments):
                        data_dict[f'top{idx+1}_cmt'] = top_comments[idx]['text']
                        data_dict[f'top{idx+1}_likes'] = top_comments[idx]['likes_num']
                    else:
                        data_dict[f'top{idx+1}_cmt'] = ''
                        data_dict[f'top{idx+1}_likes'] = 0

                # Cập nhật DB (hàm đã fix sẽ reset ai_status = 'pending')
                if update_rescraped_metadata(vid, data_dict):
                    print(f"  [✅] Đã cập nhật DB và reset ai_status = 'pending'")
                    updated += 1
                else:
                    print(f"  [❌] Lỗi khi cập nhật DB")
                    failed += 1

                # Nghỉ ngẫu nhiên để tránh bị chặn
                time.sleep(random.uniform(5.0, 10.0))

            except Exception as e:
                print(f"  [🔥] Lỗi: {e}")
                failed += 1
                continue

    finally:
        print("\n[*] Đang đóng trình duyệt...")
        try:
            driver.quit()
        except:
            pass

    print(f"\n{'=' * 60}")
    print(f"📊 BÁO CÁO:")
    print(f"   ✅ Cập nhật thành công: {updated}/{len(videos)}")
    print(f"   ❌ Thất bại: {failed}/{len(videos)}")
    print(f"{'=' * 60}")

    if updated > 0:
        print(f"\n👉 Chạy lại AI pipeline để phân tích sentiment:")
        print(f"   python -m services.ai_engine.ai_core_main")


if __name__ == "__main__":
    main()
