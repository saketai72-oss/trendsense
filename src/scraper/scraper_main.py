import sys
import os

# Thêm đường dẫn gốc trước khi import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import random
import requests
from datetime import datetime

try:
    from langdetect import detect, LangDetectException
except ImportError:
    print("[!] Thiếu thư viện langdetect. Hãy chạy: pip install langdetect")
    sys.exit(1)

from config import settings
from src.scraper.browser import init_driver
from src.scraper.database import init_db, extract_video_id, mark_as_scraped, insert_video_metadata
from src.scraper.link_crawler import get_trending_links
from src.scraper.content_parser import extract_basic_stats, extract_top_comments



def _trigger_modal(video_id, url, video_data, top_comments):
    """
    Gửi nhỏ giọt (drip-feed) từng video sang Modal AI Core.
    Fire-and-forget: Modal spawn GPU worker bất đồng bộ.
    Nếu MODAL_WEBHOOK_URL không được cấu hình → bỏ qua.
    """
    modal_url = settings.MODAL_WEBHOOK_URL
    if not modal_url:
        return

    payload = {
        "video_id": video_id,
        "url": url,
        "caption": video_data.get("caption", ""),
        "views": video_data.get("views", 0),
        "likes": video_data.get("likes", 0),
        "comments": video_data.get("comments", 0),
        "shares": video_data.get("shares", 0),
        "saves": video_data.get("saves", 0),
        "create_time": video_data.get("create_time", 0),
        "top_comments": [
            {"text": c.get("text", ""), "likes": c.get("likes_num", 0)}
            for c in (top_comments or [])
        ],
    }

    try:
        resp = requests.post(modal_url, json=payload, timeout=15)
        if resp.status_code == 200:
            result = resp.json()
            print(f"  [🚀] Đã gửi sang Modal AI → {result.get('status', 'ok')}")
        else:
            print(f"  [!] Modal HTTP {resp.status_code}: {resp.text[:80]}")
    except requests.exceptions.Timeout:
        print(f"  [!] Modal timeout (vẫn có thể đã nhận request).")
    except Exception as e:
        print(f"  [!] Lỗi kết nối Modal: {str(e)[:60]}")


def main():
    init_db()
    driver = init_driver()
    try:
        # TĂNG TỶ LỆ VIDEO VIỆT NAM (Tránh lỗi do bắt IP quốc tế)
        vn_tags = ["xuhuong", "xuhuongtiktok", "giaitri", "vietnam", "tintuc", "haihuoc"]
        target_tag = random.choice(vn_tags)
        url = f"https://www.tiktok.com/tag/{target_tag}"
        
        driver.get(url)
        print(f"👉 Đang tải TikTok hashtag: #{target_tag} (Đảm bảo content Việt)...")
        time.sleep(5)  # Giảm từ 8s → 5s (headless eager load nhanh hơn)
    except Exception as e:
        print(f"[!] Lỗi khi tải trang hashtag (Timeout?): {e}")

    # 1. Thu thập POOL link dự phòng (gấp 3x target)
    links = get_trending_links(driver, target_count=settings.MAX_VIDEOS)

    print("\n===== BẮT ĐẦU THU THẬP DỮ LIỆU =====\n")
    today = datetime.now().date().isoformat()
    saved_count = 0
    skipped_lang = 0
    target = settings.MAX_VIDEOS

    # 2. Duyệt pool link — DỪNG SỚM khi đủ target video Việt
    for i, link in enumerate(links, 1):
        # ĐỦ RỒI → dừng sớm, không cào thêm
        if saved_count >= target:
            print(f"\n[✓] Đã đủ {target} video Việt — Dừng cào sớm!")
            break

        print(f"\n[{i}/{len(links)}] Đang cào: {link}  (Đã lưu: {saved_count}/{target})")
        try:
            driver.get(link)
            time.sleep(2.5)  # Giảm từ 4s → 2.5s (eager strategy đã tải DOM xong)
        except Exception as e:
            print(f"  [!] Gặp lỗi khi truy cập link (Timeout video này): {e} -> Bỏ qua.")
            continue

        # Bóc tách các chỉ số cơ bản
        stats = extract_basic_stats(driver.page_source)

        # === BỘ LỌC NGÔN NGỮ (TRƯỚC KHI CÀO COMMENTS — TIẾT KIỆM THỜI GIAN) ===
        caption_text = stats.get('Caption', '').strip()
        if caption_text:
            try:
                lang = detect(caption_text)
                if lang != 'vi':
                    skipped_lang += 1
                    print(f"  [✂️] Bỏ qua video quốc tế (Ngôn ngữ: {lang}). Đã bỏ qua: {skipped_lang}")
                    
                    # Vẫn đánh dấu là đã cào để không bị lặp lại lần sau
                    video_id = extract_video_id(link)
                    if video_id:
                        mark_as_scraped(video_id)
                    continue
            except LangDetectException:
                # Nếu caption chỉ toàn emoji hoặc số (không detect được) → cho qua
                pass

        # Bóc tách Top 5 bình luận (CHỈ chạy cho video đã qua bộ lọc ngôn ngữ)
        has_comments = stats['Comments'] > 0
        top_5_comments = extract_top_comments(driver, has_comments)

        # 3. Đóng gói dữ liệu và ghi vào Postgres
        video_id = extract_video_id(link)
        if video_id:
            print(f"  [*] Đang xử lý ID {video_id}...")

            # Chuẩn bị data cho database
            video_data = {
                'link': link,
                'create_time': int(stats['Create_Time'] or 0),
                'caption': stats['Caption'],
                'views': stats['Views'],
                'likes': stats['Likes'],
                'comments': stats['Comments'],
                'shares': stats['Shares'],
                'saves': stats['Saves'],
                'scrape_date': today,
            }

            # Gắn top comments
            for idx in range(5):
                if idx < len(top_5_comments):
                    video_data[f'top{idx+1}_cmt'] = top_5_comments[idx]['text']
                    video_data[f'top{idx+1}_likes'] = top_5_comments[idx]['likes_num']
                else:
                    video_data[f'top{idx+1}_cmt'] = ""
                    video_data[f'top{idx+1}_likes'] = 0

            # Ghi vào PostgreSQL
            success = insert_video_metadata(video_id, video_data)
            
            if success:
                saved_count += 1
                print(f"  [✓] Đã lưu metadata video {video_id} vào DB. ({saved_count}/{target})")
                
                # CHỈ khi lưu DB thành công mới đánh dấu history để không cào lại
                mark_as_scraped(video_id)
                
                # 🚀 Nhỏ giọt: Gửi video này sang Modal AI Core xử lý
                _trigger_modal(video_id, link, video_data, top_5_comments)
            else:
                print(f"  [!] Thất bại khi lưu video {video_id} vào DB. Sẽ không đánh dấu history.")


    # 4. Dọn dẹp
    print("\n[*] Đang đóng trình duyệt...")
    try:
        driver.quit()
    except Exception as e:
        # Lỗi handle invalid trên Windows thường không gây hại, ta có thể bỏ qua
        pass

    # 5. Báo cáo kết quả
    print(f"\n{'=' * 50}")
    print(f"📊 BÁO CÁO MẺ CÀO:")
    print(f"   🔗 Tổng link duyệt: {min(i if 'i' in dir() else len(links), len(links))}")
    print(f"   ✅ Video Việt đã lưu: {saved_count}/{target}")
    print(f"   ✂️  Video quốc tế bị lọc: {skipped_lang}")
    print(f"{'=' * 50}")

    if saved_count == 0 and len(links) > 0:
        print("[!] CẢNH BÁO: Tìm thấy link nhưng không lưu được video nào.")
        print("    → Nguyên nhân có thể: Toàn video quốc tế hoặc trùng ID trong DB.")
    
    print(f"\n[+] ĐÃ XONG MẺ CÀO NÀY! Lưu {saved_count} video vào database.")


if __name__ == "__main__":
    main()