import sys
import os

# Thêm đường dẫn gốc trước khi import local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
import random
import requests
import json
from datetime import datetime

try:
    from langdetect import detect, LangDetectException
except ImportError:
    print("[!] Thiếu thư viện langdetect. Hãy chạy: pip install langdetect")
    sys.exit(1)

from core.config import service_settings as settings
from services.tiktok_scraper.browser import init_driver, get_random_proxy, is_blocked
from core.db.models import extract_video_id, mark_as_scraped, insert_video_metadata
from services.tiktok_scraper.link_crawler import get_trending_links
from services.tiktok_scraper.content_parser import extract_basic_stats




STANDARD_CATEGORIES = [
    "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
    "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
    "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
]

OPENROUTER_FREE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "deepseek/deepseek-v4-flash:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
]


def _call_llm_json(prompt: str, system: str = "Bạn là AI phân tích xu hướng TikTok. Chỉ trả về JSON hợp lệ.") -> dict:
    """
    Gọi OpenRouter (10 free models) → Groq fallback.
    Trả về dict JSON đã parse. Raise nếu tất cả đều thất bại.
    """
    import re

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    def _extract_json(text: str) -> dict:
        start = text.find('{')
        if start == -1:
            raise ValueError("No JSON object found")
        brace_count = 0
        end = None
        for i in range(start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i
                    break
        if end is None:
            raise ValueError("Unbalanced braces")
        json_str = re.sub(r'\\u\{([0-9A-Fa-f]+)\}', lambda m: f"\\u{m.group(1).zfill(4)}", text[start:end+1])
        return json.loads(json_str)

    # 1. OpenRouter
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1")
            for model_name in OPENROUTER_FREE_MODELS:
                try:
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        temperature=0.5,
                        max_tokens=800,
                    )
                    content = resp.choices[0].message.content
                    if content:
                        result = _extract_json(content)
                        print(f"  [🤖] OpenRouter ({model_name.split('/')[-1]}) → OK")
                        return result
                except Exception as e:
                    print(f"  [~] OpenRouter {model_name.split('/')[-1]}: {str(e)[:60]}")
                    continue
        except Exception as e:
            print(f"  [!] OpenRouter config error: {str(e)[:60]}")

    # 2. Groq fallback
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            groq_client = Groq(api_key=groq_key)
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.5,
                max_tokens=800,
            )
            content = resp.choices[0].message.content
            if content:
                result = _extract_json(content)
                print(f"  [🤖] Groq (llama-3.3-70b) → OK")
                return result
        except Exception as e:
            print(f"  [!] Groq fallback error: {str(e)[:60]}")

    raise RuntimeError("Tất cả LLM providers đều thất bại (OpenRouter + Groq)")


def _fallback_llm_analysis(video_id, url, video_data, top_comments):
    """
    Phân tích video bằng OpenRouter/Groq (text-only, không cần video gốc).
    Dùng khi Gemini Backend không khả dụng.
    """
    from services.ai_engine.math_utils import calculate_metrics

    caption = video_data.get("caption", "")
    views = video_data.get("views", 0)
    likes = video_data.get("likes", 0)
    comments_count = video_data.get("comments", 0)
    shares = video_data.get("shares", 0)
    saves = video_data.get("saves", 0)

    prompt = f"""Phân tích video TikTok dựa trên các thông tin sau (không có nội dung video gốc):

Caption: {caption}
Top bình luận: {json.dumps([{"text": c.get("text", ""), "likes": c.get("likes_num", 0)} for c in (top_comments or [])[:5]], ensure_ascii=False)}
Lượt xem: {views:,}, thích: {likes:,}, bình luận: {comments_count:,}, chia sẻ: {shares:,}, lưu: {saves:,}

Hãy trả về JSON với các trường:
- summary (string, tóm tắt ngắn ~20 từ, tiếng Việt)
- category (string, chọn từ danh sách: {', '.join(STANDARD_CATEGORIES)})
- sentiment (string, một trong "🟢 TÍCH CỰC", "🟡 TRUNG LẬP", "🔴 TIÊU CỰC")
- positive_score (float, 0-100)
- keywords (list of strings, 3-5 từ khóa tiếng Việt)
- audio_transcript (string, để trống "")
"""

    def _normalize_sentiment(sentiment: str) -> str:
        if not sentiment:
            return "🟡 TRUNG LẬP"
        s = sentiment.lower()
        if any(term in s for term in ["tích cực", "positive", "vui", "tốt"]):
            return "🟢 TÍCH CỰC"
        elif any(term in s for term in ["tiêu cực", "negative", "buồn", "xấu"]):
            return "🔴 TIÊU CỰC"
        else:
            return "🟡 TRUNG LẬP"

    try:
        result = _call_llm_json(prompt)

        # Validate category
        cat = result.get("category", "🌍 Khác")
        matched = "🌍 Khác"
        for std in STANDARD_CATEGORIES:
            if std.lower() == cat.lower() or (" " in std and std.split(" ", 1)[-1].lower() in cat.lower()):
                matched = std
                break

        # Tính metrics
        vph, er, velocity = calculate_metrics(
            views=views, likes=likes, comments=comments_count,
            shares=shares, saves=saves,
            create_time=video_data.get("create_time", 0)
        )

        final_data = {
            "video_description": result.get("summary", ""),
            "category": matched,
            "video_sentiment": _normalize_sentiment(result.get("sentiment", "🟡 TRUNG LẬP")),
            "positive_score": float(result.get("positive_score", 50.0)),
            "top_keywords": ", ".join(result.get("keywords", [])[:5]),
            "audio_transcript": result.get("audio_transcript", ""),
            "ai_status": "completed",
            "views_per_hour": vph,
            "engagement_rate": er,
            "viral_velocity": velocity,
        }

        from core.db.models import update_ai_results
        update_ai_results(video_id, final_data)
        print(f"  [✅] Fallback LLM thành công cho {video_id}")
        return True

    except Exception as e:
        print(f"  [❌] Fallback LLM thất bại cho {video_id}: {str(e)[:80]}")
        try:
            from core.db.models import update_ai_results
            update_ai_results(video_id, {
                "video_description": f"Lỗi phân tích: {str(e)[:60]}",
                "category": "Lỗi",
                "video_sentiment": "🟡 TRUNG LẬP",
                "positive_score": 50.0,
                "ai_status": "error",
            })
        except Exception:
            pass
        return False


def _trigger_ai_pipeline(video_id, url, video_data, top_comments):
    """
    Gửi nhỏ giọt (drip-feed) từng video sang Backend (Gemini 2.5 Flash).
    Nếu Backend chết hoặc lỗi hệ thống → Fallback sang OpenRouter/Groq (text-only).
    Modal KHÔNG được sử dụng cho scraper — chỉ dành cho user upload.
    """
    gemini_url = os.getenv("GEMINI_WEBHOOK_URL", "https://trendsense-sfj6.onrender.com/api/analyze-gemini")

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
        resp = requests.post(gemini_url, json=payload, timeout=5)

        if resp.status_code == 202:
            print(f"  [🚀] Đã gửi sang Gemini AI Backend → Accepted")
            return

        elif resp.status_code in [429, 500, 502, 503, 504]:
            print(f"  [!] Gemini Backend lỗi hệ thống ({resp.status_code}). Fallback sang OpenRouter/Groq...")
            raise RuntimeError("Backend Error")
        else:
            print(f"  [!] Gemini Backend lỗi logic ({resp.status_code}): {resp.text[:80]}. KHÔNG Fallback.")
            return

    except Exception as e:
        print(f"  [⚠️] Gemini Backend không khả dụng ({str(e)[:40]}). Kích hoạt Fallback OpenRouter/Groq...")
        _fallback_llm_analysis(video_id, url, video_data, top_comments)



def _check_ci_environment(proxy):
    """Kiểm tra nếu đang chạy trên CI mà không có proxy → cảnh báo sớm."""
    is_ci = os.environ.get("CI", "").lower() == "true" or os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    if is_ci and not proxy:
        print("=" * 60)
        print("[⚠️] CẢNH BÁO: Đang chạy trên CI (GitHub Actions) mà KHÔNG CÓ PROXY!")
        print("    TikTok chặn IP datacenter — kết quả sẽ rất kém.")
        print("    → Thêm residential proxy vào secret PROXY_LIST:")
        print('      ["http://user:pass@residential-host:port"]')
        print("    → Dịch vụ khuyên dùng: Webshare.io (free tier), Bright Data, SmartProxy")
        print("=" * 60)
    return is_ci


def _load_page_with_retry(driver, url, max_retries=3, wait=3):
    """Tải trang với retry + backoff. Trả về True nếu thành công."""
    for attempt in range(1, max_retries + 1):
        try:
            driver.get(url)
            time.sleep(wait + random.uniform(0.5, 2.0))  # Jitter để tránh pattern

            page_title = (driver.title or "").lower()

            # Trang không load được
            if "can't be reached" in page_title or "not available" in page_title:
                if attempt < max_retries:
                    print(f"  [⟳] Trang không load (attempt {attempt}/{max_retries}). Thử lại sau {wait * attempt}s...")
                    time.sleep(wait * attempt)
                    continue
                print(f"[!] ❌ Trang không load được sau {max_retries} lần.")
                print(f"    Tiêu đề: {driver.title}")
                return False

            # Bị block
            if is_blocked(driver):
                if attempt < max_retries:
                    print(f"  [⟳] Bị block (attempt {attempt}/{max_retries}). Thử lại sau {wait * attempt}s...")
                    time.sleep(wait * attempt * 2)  # Chờ lâu hơn khi bị block
                    continue
                print(f"[!] ❌ Bị block sau {max_retries} lần. Cần thay proxy.")
                return False

            return True

        except Exception as e:
            if attempt < max_retries:
                print(f"  [⟳] Lỗi tải trang (attempt {attempt}/{max_retries}): {str(e)[:100]}")
                time.sleep(wait * attempt)
                continue
            print(f"[!] ❌ Lỗi tải trang sau {max_retries} lần: {e}")
            return False

    return False


def main():
    proxy = get_random_proxy()
    is_ci = _check_ci_environment(proxy)

    # ── Kiểm tra hàng đợi trước khi khởi động browser ──────────────────────
    queue_file = os.path.join(os.path.dirname(__file__), "video_queue.json")
    _pre_queue_links = []
    _pre_queue_stats = {}
    try:
        if os.path.exists(queue_file):
            with open(queue_file, "r", encoding="utf-8") as _f:
                _qd = json.load(_f)
            _pre_queue_links = _qd.get("links", [])
            _pre_queue_stats = _qd.get("stats", {})
    except Exception:
        pass

    queue_only_mode = len(_pre_queue_links) >= settings.MAX_VIDEOS

    if queue_only_mode:
        print(f"\n[📦] Hàng đợi có {len(_pre_queue_links)} video (>= {settings.MAX_VIDEOS} mong muốn).")
        print(f"[⚡] Bỏ qua bước scraping và không khởi động browser.\n")
        driver = None
    else:
        driver = init_driver(proxy=proxy)

        # TĂNG TỶ LỆ VIDEO VIỆT NAM (Tránh lỗi do bắt IP quốc tế)
        vn_tags = ["xuhuong", "xuhuongtiktok", "giaitri", "vietnam", "tintuc", "haihuoc"]
        target_tag = random.choice(vn_tags)
        url = f"https://www.tiktok.com/tag/{target_tag}"

        print(f"👉 Đang tải TikTok hashtag: #{target_tag}...")
        if not _load_page_with_retry(driver, url):
            driver.quit()
            sys.exit(1)


    # 1. Resolve links & stats (dùng kết quả kiểm tra queue ở trên)
    links = []
    api_stats = {}

    if queue_only_mode:
        # Queue đủ — dùng toàn bộ từ queue, không scrape
        links = _pre_queue_links
        api_stats = _pre_queue_stats
    else:
        # Scrape mới và ghép queue cũ (nếu có) vào trước
        fresh_links, fresh_stats = get_trending_links(driver, target_count=settings.MAX_VIDEOS)
        if _pre_queue_links:
            deduped_queue = [ql for ql in _pre_queue_links if ql not in fresh_links]
            links = deduped_queue + fresh_links
            api_stats = {**fresh_stats, **_pre_queue_stats}
            if deduped_queue:
                print(f"  [📥] Ghép {len(deduped_queue)} video từ queue + {len(fresh_links)} video mới.")
        else:
            links = fresh_links
            api_stats = fresh_stats

    if api_stats:
        print(f"  [📊] Có stats cho {len(api_stats)} video từ TikTokApi/queue.")


    print("\n===== BẮT ĐẦU THU THẬP DỮ LIỆU =====\n")
    today = datetime.now().date().isoformat()
    saved_count = 0
    skipped_lang = 0
    target = settings.MAX_VIDEOS

    # 2. Duyệt pool link — DỪNG SỚM khi đủ target video Việt
    for i, link in enumerate(links, 1):
        is_from_api = False  # Flag: True nếu dữ liệu lấy từ TikTokApi (bỏ qua langdetect)
        # ĐỦ RỒI → dừng sớm, không cào thêm
        if saved_count >= target:
            print(f"\n[✓] Đã đủ {target} video Việt — Dừng cào sớm!")
            break

        print(f"\n[{i}/{len(links)}] Đang cào: {link}  (Đã lưu: {saved_count}/{target})")

        clean_link = link.split('?')[0]
        
        # 1. Chạy bằng Selenium trước (để lấy cả comment và stats)
        page_loaded = False
        for attempt in range(1, 4):
            try:
                driver.get(link)
                # Đợi trang ổn định và hydrate JSON
                time.sleep(5.0 + random.uniform(0, 2.0))

                if is_blocked(driver):
                    if attempt < 3:
                        print(f"  [⟳] Bị block khi tải video (attempt {attempt}/3). Chờ {5 * attempt}s...")
                        time.sleep(5 * attempt)
                        continue
                    print(f"  [🚫] Bị block! Dừng cào bằng Selenium — sẽ thử fallback sang API.")
                    break
                page_loaded = True
                break
            except Exception as e:
                if attempt < 3:
                    print(f"  [⟳] Lỗi tải video (attempt {attempt}/3): {str(e)[:80]}")
                    time.sleep(3 * attempt)
                    continue
                print(f"  [!] Lỗi Selenium tải video sau 3 lần thử: {str(e)[:80]}")

        # 2. Xử lý logic fallback
        stats = {}
        if page_loaded:
            # Bóc tách stats từ Selenium
            stats = extract_basic_stats(driver.page_source)
            
            # NẾU Selenium parse lỗi (Views = 0) NHƯNG có data từ TikTokApi -> ƯU TIÊN dùng TikTokApi
            if int(stats.get('Views', 0)) <= 0 and clean_link in api_stats:
                api_data = api_stats[clean_link]
                stats = {
                    'Caption': api_data.get('caption', stats.get('Caption', '')),
                    'Views': api_data.get('views', 0),
                    'Likes': api_data.get('likes', 0),
                    'Comments': api_data.get('comments', 0),
                    'Shares': api_data.get('shares', 0),
                    'Saves': api_data.get('saves', 0),
                    'Create_Time': str(api_data.get('create_time', stats.get('Create_Time', '0'))),
                }
                is_from_api = True
                print(f"  [📊] Stats (Selenium lỗi, dùng TikTokApi): 👁️{stats['Views']:,} | ❤️{stats['Likes']:,} | 💬{stats['Comments']:,}")
            else:
                print(f"  [📊] Stats (từ Selenium): 👁️{stats.get('Views', 0):,} | ❤️{stats.get('Likes', 0):,} | 💬{stats.get('Comments', 0):,}")
        else:
            # Fallback sang TikTokApi nếu Selenium hoàn toàn không tải được trang
            if clean_link in api_stats:
                api_data = api_stats[clean_link]
                stats = {
                    'Caption': api_data.get('caption', ''),
                    'Views': api_data.get('views', 0),
                    'Likes': api_data.get('likes', 0),
                    'Comments': api_data.get('comments', 0),
                    'Shares': api_data.get('shares', 0),
                    'Saves': api_data.get('saves', 0),
                    'Create_Time': str(api_data.get('create_time', 0)),
                }
                is_from_api = True
                print(f"  [📊] Stats (từ TikTokApi - Fallback): 👁️{stats['Views']:,} | ❤️{stats['Likes']:,} | 💬{stats['Comments']:,}")
            else:
                if is_blocked(driver):
                    break # Dừng cào hoàn toàn nếu block và không có fallback
                print("  [!] Không có dữ liệu TikTokApi fallback. Bỏ qua video này.")
                continue

        # === KIỂM TRA DỮ LIỆU HỢP LỆ ===
        views = int(stats.get('Views', 0))
        likes = int(stats.get('Likes', 0))
        comments_count = int(stats.get('Comments', 0))
        shares = int(stats.get('Shares', 0))
        saves = int(stats.get('Saves', 0))

        print(f"  [📊] Stats: 👁️{views:,} | ❤️{likes:,} | 💬{comments_count:,} | 🔗{shares:,} | 📌{saves:,}")

        if views <= 0:
            print(f"  [✂️] Bỏ qua: Views = 0 (video bị ẩn hoặc lỗi parse).")
            continue

        if likes > views:
            print(f"  [✂️] Bỏ qua: Likes ({likes:,}) > Views ({views:,}) — Dữ liệu bất thường.")
            video_id = extract_video_id(link)
            if video_id:
                mark_as_scraped(video_id)
            continue

        if comments_count > views:
            print(f"  [✂️] Bỏ qua: Comments ({comments_count:,}) > Views ({views:,}) — Dữ liệu bất thường.")
            video_id = extract_video_id(link)
            if video_id:
                mark_as_scraped(video_id)
            continue

        # === BỘ LỌC NGÔN NGỮ (TRƯỚC KHI CÀO COMMENTS — TIẾT KIỆM THỜI GIAN) ===
        # Nếu dữ liệu đến từ TikTokApi (đã lọc đúng hashtag Việt), bỏ qua kiểm tra ngôn ngữ
        if not is_from_api:
            caption_text = str(stats.get('Caption', '')).strip()
            if caption_text:
                # Bước 1: Kiểm tra ký tự đặc trưng tiếng Việt (có dấu)
                from core.utils.lang_utils import is_vietnamese_text
                viet_char_check = is_vietnamese_text(caption_text)
                if viet_char_check is True:
                    # Chắc chắn là tiếng Việt → giữ lại, không cần langdetect
                    pass
                else:
                    # Không có dấu tiếng Việt → dùng langdetect làm fallback
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

        # 3. Đóng gói dữ liệu và ghi vào Postgres (không cào bình luận)
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

            # Ghi vào PostgreSQL
            success = insert_video_metadata(video_id, video_data)
            
            if success:
                saved_count += 1
                print(f"  [✓] Đã lưu metadata video {video_id} vào DB. ({saved_count}/{target})")
                
                # CHỈ khi lưu DB thành công mới đánh dấu history để không cào lại
                mark_as_scraped(video_id)
                
                # 🚀 Nhỏ giọt: Gửi video này sang Modal AI Core xử lý
                _trigger_ai_pipeline(video_id, link, video_data, [])
            else:
                print(f"  [!] Thất bại khi lưu video {video_id} vào DB. Sẽ không đánh dấu history.")


    # 4. Dọn dẹp & Lưu Queue
    if driver is not None:
        print("\n[*] Đang đóng trình duyệt...")
        try:
            driver.quit()
        except Exception:
            pass  # Lỗi handle invalid trên Windows — không gây hại
        
    # Xử lý hàng đợi sau khi chạy xong
    try:
        # Tính index dừng: nếu đủ target thì dừng tại i-1, không thì đã chạy hết links
        last_processed = (i - 1) if saved_count >= target else i
        remaining_links = links[last_processed:]

        if remaining_links:
            # Còn link chưa xử lý → lưu vào queue cho lần sau
            queue_stats = {lnk: api_stats[lnk] for lnk in remaining_links if lnk in api_stats}
            with open(queue_file, "w", encoding="utf-8") as f:
                json.dump({"links": remaining_links, "stats": queue_stats}, f, ensure_ascii=False, indent=2)
            print(f"\n[💾] Lưu {len(remaining_links)} video thừa vào hàng đợi cho lần chạy sau.")
        else:
            # Không còn gì thừa → xóa queue cũ (nếu có)
            if os.path.exists(queue_file):
                os.remove(queue_file)
                print(f"\n[🗑️] Đã xóa hàng đợi (đã dùng hết).")
            else:
                print(f"\n[✓] Không có hàng đợi để xóa.")
    except Exception as e:
        print(f"  [!] Lỗi khi cập nhật video_queue.json: {e}")


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