"""
AI Core Main — Luồng Inference chạy mỗi 4 giờ.
1. Đọc video MỚI chưa phân tích từ SQLite
2. Chạy NLP Sentiment CHỈ trên comment chưa xử lý (cache)
3. Predict viral probability bằng model đã train sẵn
4. Ghi kết quả ngược lại vào SQLite
5. Zero-shot AI phân loại danh mục (KHÔNG cho phép "🌍 Khác")
6. Tải video viral 480p
7. Multimodal AI phân tích nội dung
7.5. ÉP BUỘC phân loại lại video "🌍 Khác" — CLIP Vision + Ollama tie-breaker
8. Smart Keywords cho Top 20 viral videos (NER + POS-tag)
"""
import pandas as pd
import os
import sys
import requests
from collections import Counter

# Nạp config từ thư mục gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# Nạp database
sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
from database import init_db, get_unanalyzed_videos, update_sentiment, \
    update_predictions_batch, get_all_analyzed_videos, \
    get_videos_without_category, update_categories_batch, reset_all_analysis_status, \
    get_videos_with_khac_category, update_category

# Nạp các module AI tự viết
from math_utils import calculate_metrics
from nlp_utils import clean_text, extract_keywords, extract_smart_keywords
from sentiment_engine import analyze_batch
from prediction_engine import run_viral_prediction
from categorizer import categorize_by_ai


# =====================================================
# BƯỚC 7.5: ÉP BUỘC PHÂN LOẠI LẠI VIDEO "🌍 KHÁC"
# Chiến thuật: CLIP Vision → Ollama LLM tie-breaker
# =====================================================

# 11 danh mục hợp lệ (KHÔNG BAO GỒM "Khác")
VALID_CATEGORIES = [
    "🎭 Giải trí", "🎵 Âm nhạc", "🍳 Ẩm thực", "💻 Công nghệ",
    "👗 Thời trang", "📚 Giáo dục", "🏋️ Thể thao", "🐾 Động vật",
    "💄 Làm đẹp", "📰 Tin tức", "💰 Tài chính",
]


def _ollama_classify(audio_text, ocr_text, blip_text, caption):
    """
    Tie-breaker: Dùng Ollama (Llama-3) phân loại khi CLIP Vision không đủ tự tin.
    Gửi thông tin Whisper (âm thanh) + OCR (chữ) + BLIP (bối cảnh) → LLM chọn 1 danh mục.
    """
    categories_str = "\n".join([f"  - {cat}" for cat in VALID_CATEGORIES])

    prompt = f"""Bạn là trợ lý AI phân loại video TikTok.
Dưới đây là thông tin trích xuất từ VIDEO:
1. Âm thanh nghe được: {audio_text[:200] if audio_text else 'Không có'}
2. Chữ trên màn hình (OCR): {ocr_text[:200] if ocr_text else 'Không có'}
3. AI Vision nhìn thấy: {blip_text[:200] if blip_text else 'Không có'}
4. Tiêu đề gốc: {caption[:200] if caption else 'Không có'}

DANH MỤC HỢP LỆ (chỉ được chọn 1 trong số này):
{categories_str}

QUY TẮC: Chọn ĐÚNG 1 danh mục phù hợp nhất. Chỉ xuất ra tên danh mục, KHÔNG giải thích.
TUYỆT ĐỐI KHÔNG được chọn "Khác" hoặc bất kỳ danh mục nào ngoài danh sách trên."""

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        if response.status_code == 200:
            result = response.json().get('response', '').strip()
            # Tìm danh mục hợp lệ trong output
            for cat in VALID_CATEGORIES:
                if cat in result:
                    return cat
            # Nếu LLM trả về text lạ, thử match từng phần
            for cat in VALID_CATEGORIES:
                cat_name = cat.split(' ', 1)[1] if ' ' in cat else cat
                if cat_name.lower() in result.lower():
                    return cat
        else:
            print(f"    [!] Lỗi Ollama (HTTP {response.status_code}): {response.text[:100]}")
    except requests.exceptions.RequestException as e:
        print(f"    [!] Lỗi Timeout/Kết nối Ollama: {str(e)[:50]}")

    return None  # LLM cũng không phân loại được


def force_reclassify_khac_videos():
    """
    BƯỚC 7.5: Loại bỏ hoàn toàn danh mục "🌍 Khác".
    Pipeline: Tải video → CLIP Vision → Ollama tie-breaker → Force top-1.
    """
    khac_videos = get_videos_with_khac_category()

    if not khac_videos:
        print("[✓] 🏷️ Không còn video nào mang danh mục 'Khác'. Tuyệt vời!")
        return

    print(f"\n{'=' * 60}")
    print(f"🏷️ ÉP BUỘC PHÂN LOẠI LẠI {len(khac_videos)} VIDEO 'KHÁC'")
    print(f"{'=' * 60}")

    # --- Bước 1: Tải video chưa có MP4 ---
    try:
        from video_downloader import download_for_khac_category
        khac_videos = download_for_khac_category()
    except Exception as e:
        print(f"    [!] Lỗi tải video Khác: {e}")

    if not khac_videos:
        print("[*] Không còn video Khác sau khi refresh.")
        return

    # --- Bước 2: Load CLIP model ---
    clip_classifier = None
    try:
        from vision_engine import _load_clip_classifier, extract_keyframes, force_classify_by_vision
        clip_classifier = _load_clip_classifier()
    except Exception as e:
        print(f"    [!] Không load được CLIP: {e}")

    # --- Bước 3: Load Multimodal components (cho Ollama tie-breaker) ---
    has_multimodal = False
    try:
        from multimodal_engine import extract_audio_and_transcribe, extract_frames, run_blip, run_ocr
        has_multimodal = True
    except ImportError:
        print("    [!] Thiếu multimodal_engine, chỉ dùng CLIP Vision.")

    reclassified = 0

    for i, video in enumerate(khac_videos, 1):
        vid = video['video_id']
        caption = video.get('caption', '')
        video_path = video.get('video_path', '')

        print(f"\n  [{i}/{len(khac_videos)}] Video Khác: {vid}")

        new_category = None
        confidence = 0.0

        # --- Chiến thuật 1: CLIP Vision (nếu có file MP4) ---
        if video_path and os.path.exists(str(video_path)) and clip_classifier:
            try:
                frames = extract_keyframes(video_path)
                if frames:
                    new_category, confidence = force_classify_by_vision(frames, clip_classifier)
                    if new_category and confidence >= settings.VISION_CATEGORY_OVERRIDE_THRESHOLD:
                        print(f"    ✅ CLIP Vision: {new_category} (confidence: {confidence:.1%})")
                    elif new_category:
                        # CLIP không đủ tự tin → thử Ollama tie-breaker
                        print(f"    🤔 CLIP thiếu tự tin ({confidence:.1%}), thử Ollama...")

                        if has_multimodal:
                            try:
                                # Thu thập thông tin đa phương tiện
                                audio_t = extract_audio_and_transcribe(video_path)
                                pil_frames, cv2_frames = extract_frames(video_path)
                                blip_t = run_blip(pil_frames) if pil_frames else ""
                                ocr_t = run_ocr(cv2_frames) if cv2_frames else ""

                                ollama_result = _ollama_classify(audio_t, ocr_t, blip_t, caption)
                                if ollama_result:
                                    new_category = ollama_result
                                    print(f"    ✅ Ollama tie-breaker: {new_category}")
                                else:
                                    # Ollama cũng thất bại → giữ kết quả CLIP top-1
                                    print(f"    ⚡ Ollama thất bại, dùng CLIP top-1: {new_category}")
                            except Exception as e:
                                print(f"    [!] Lỗi Ollama: {e}, dùng CLIP top-1: {new_category}")
                        else:
                            # Không có multimodal → dùng CLIP top-1
                            print(f"    ⚡ Dùng CLIP top-1: {new_category}")
            except Exception as e:
                print(f"    [!] Lỗi CLIP: {e}")

        # --- Chiến thuật 2: Nếu không có video → dùng Ollama với caption ---
        if not new_category and has_multimodal:
            try:
                ollama_result = _ollama_classify("", "", "", caption)
                if ollama_result:
                    new_category = ollama_result
                    print(f"    ✅ Ollama (chỉ caption): {new_category}")
            except Exception:
                pass

        # --- Chiến thuật 3: Force fallback cuối cùng ---
        if not new_category:
            new_category = "🎭 Giải trí"  # Danh mục phổ biến nhất
            print(f"    ⚡ Fallback cuối: {new_category}")

        # Ghi vào DB
        update_category(vid, new_category)
        reclassified += 1
        print(f"    📝 [{video.get('category', '🌍 Khác')}] → [{new_category}]")

    print(f"\n{'=' * 60}")
    print(f"🏷️ ÉP BUỘC PHÂN LOẠI HOÀN TẤT!")
    print(f"   ✅ Đã gán danh mục mới cho {reclassified}/{len(khac_videos)} video")
    print(f"{'=' * 60}")


# =====================================================
# BƯỚC 8: SMART KEYWORDS CHO TOP VIRAL VIDEOS
# =====================================================
def refresh_smart_keywords_for_top_viral(top_n=20):
    """
    Chạy NER + POS-tag trích xuất từ khóa thông minh cho Top N video viral nhất.
    Chỉ giữ: tên riêng, địa danh, thương hiệu, sản phẩm.
    Loại bỏ: động từ, tính từ vô nghĩa.
    """
    all_videos = get_all_analyzed_videos()
    if not all_videos:
        return

    # Sắp xếp theo viral_probability giảm dần, lấy top N
    sorted_videos = sorted(all_videos, key=lambda v: v.get('viral_probability', 0), reverse=True)
    top_viral = sorted_videos[:top_n]

    print(f"\n{'=' * 50}")
    print(f"🧠 SMART KEYWORDS — Phân tích NER/POS cho Top {len(top_viral)} viral")
    print(f"{'=' * 50}")

    updated = 0
    for video in top_viral:
        vid = video['video_id']
        caption = video.get('caption', '')

        if not caption or len(str(caption).strip()) < 5:
            continue

        # Gộp caption + top comments thành 1 văn bản
        all_text = clean_text(str(caption))
        for i in range(1, 6):
            cmt = video.get(f'top{i}_cmt', '')
            if cmt and str(cmt).strip():
                all_text += " " + clean_text(str(cmt))

        # Trích xuất từ khóa thông minh (NER + POS-tag)
        smart_kws = extract_smart_keywords(all_text)
        if smart_kws:
            kw_str = ", ".join(smart_kws[:5])  # Tối đa 5 từ khóa
            # Cập nhật vào DB
            from database import _get_conn
            conn = _get_conn()
            conn.execute('UPDATE videos SET top_keywords = ? WHERE video_id = ?', (kw_str, vid))
            conn.commit()
            conn.close()
            updated += 1

    print(f"[✓] Đã cập nhật smart keywords cho {updated}/{len(top_viral)} video viral.")


# =====================================================
# PIPELINE CHÍNH
# =====================================================
def process_new_videos(force_all=False):
    """Xử lý video. Nếu force_all=True, sẽ reset toàn bộ cờ để quét lại data cũ."""
    print("\n" + "=" * 60)
    if force_all:
        print("🧠 AI CORE — CHẾ ĐỘ QUÉT LẠI TOÀN BỘ (Full Re-scan)")
    else:
        print("🧠 AI CORE — CHẾ ĐỘ INFERENCE (Chỉ xử lý video mới)")
    print("=" * 60)

    init_db()

    if force_all:
        reset_all_analysis_status()

    # 1. Lấy video chưa phân tích
    new_videos = get_unanalyzed_videos()

    if not new_videos:
        print("[*] ✅ Không có video mới cần xử lý. Mọi thứ đã cập nhật.")
        # Vẫn chạy các bước hậu xử lý (7.5, 8) dù không có video mới
        _run_post_processing()
        return

    print(f"[*] Tìm thấy {len(new_videos)} video mới chưa phân tích.")

    global_word_counter = Counter()

    # 2. Xử lý từng video: tính metrics + chuẩn bị NLP
    comments_to_analyze = []
    comment_tracker = []  # (video_index, comment_index)

    for idx, video in enumerate(new_videos):
        # Tính metrics
        views = video.get('views', 0) or 0
        likes = video.get('likes', 0) or 0
        comments = video.get('comments', 0) or 0
        shares = video.get('shares', 0) or 0
        saves = video.get('saves', 0) or 0
        create_time = video.get('create_time', 0) or 0

        views_per_hour, engagement_rate, viral_velocity = calculate_metrics(
            views=views, likes=likes, comments=comments,
            shares=shares, saves=saves, create_time=create_time
        )

        # Lưu metrics tạm vào dict
        new_videos[idx]['_views_per_hour'] = views_per_hour
        new_videos[idx]['_engagement_rate'] = engagement_rate
        new_videos[idx]['_viral_velocity'] = viral_velocity
        new_videos[idx]['_total_stars'] = 0
        new_videos[idx]['_valid_comments'] = 0

        # Xử lý top comments
        video_words = []
        for i in range(1, 6):
            raw_cmt = video.get(f'top{i}_cmt', '')
            txt = clean_text(str(raw_cmt)) if raw_cmt else ""

            if txt:
                comments_to_analyze.append(txt[:512])
                comment_tracker.append((idx, i))

                words = extract_keywords(txt)
                video_words.extend(words)

        top_video_keywords = [word for word, count in Counter(video_words).most_common(3)]
        new_videos[idx]['_top_keywords'] = ", ".join(top_video_keywords)
        global_word_counter.update(video_words)

    # 3. NLP Sentiment chạy trên TOÀN BỘ comments chưa phân tích
    if comments_to_analyze:
        print(f"[*] AI đang chấm điểm {len(comments_to_analyze)} bình luận MỚI...")
        ai_results = analyze_batch(comments_to_analyze)

        if ai_results:
            for (vid_idx, cmt_idx), res in zip(comment_tracker, ai_results):
                stars = int(res['label'].split()[0])
                new_videos[vid_idx]['_total_stars'] += stars
                new_videos[vid_idx]['_valid_comments'] += 1
    else:
        print("[*] Không có bình luận mới cần phân tích NLP.")

    # 4. Tổng hợp điểm & ghi kết quả vào SQLite
    print("[*] Đang lưu kết quả phân tích vào SQLite...")
    for video in new_videos:
        total_stars = video['_total_stars']
        valid_comments = video['_valid_comments']

        if valid_comments > 0:
            avg_stars = total_stars / valid_comments
            positive_score = round((avg_stars / 5) * 100, 2)

            if avg_stars >= 3.5:
                sentiment = "🟢 TÍCH CỰC"
            elif avg_stars <= 2.5:
                sentiment = "🔴 TIÊU CỰC"
            else:
                sentiment = "🟡 TRUNG LẬP"
        else:
            positive_score = 0
            sentiment = "⚪ KHÔNG CÓ BÌNH LUẬN"

        # Ghi vào SQLite + đánh cờ sentiment_analyzed = 1
        update_sentiment(video['video_id'], {
            'views_per_hour': video['_views_per_hour'],
            'engagement_rate': video['_engagement_rate'],
            'viral_velocity': video['_viral_velocity'],
            'positive_score': positive_score,
            'video_sentiment': sentiment,
            'top_keywords': video['_top_keywords'],
        })

    print(f"[✓] Đã phân tích xong {len(new_videos)} video mới.")

    # 5. Predict viral bằng model sẵn trên TOÀN BỘ video đã xử lý
    print("\n[*] Đang predict xác suất viral cho toàn bộ video...")
    all_videos = get_all_analyzed_videos()

    if all_videos:
        df_all = pd.DataFrame(all_videos)
        df_result = run_viral_prediction(df_all)

        # Ghi kết quả predict ngược lại SQLite
        if 'viral_probability' in df_result.columns:
            predictions = [
                (row['viral_probability'], row['video_id'])
                for _, row in df_result.iterrows()
                if pd.notna(row.get('viral_probability'))
            ]
            if predictions:
                update_predictions_batch(predictions)

    # 6. In thống kê
    if global_word_counter:
        print("\n" + "=" * 40)
        print("🔥 TOP 15 TỪ KHÓA XUẤT HIỆN NHIỀU NHẤT (batch mới):")
        for word, count in global_word_counter.most_common(15):
            print(f"   - {word.replace('_', ' ')}: {count} lần")
        print("=" * 40)

    # 7. Zero-shot AI cho video chưa gắn mác (hoặc đang là "🌍 Khác")
    uncategorized = get_videos_without_category()
    if uncategorized:
        print(f"\n🧠 AI Zero-shot: Phân loại {len(uncategorized)} video chưa gắn mác...")
        captions_with_ids = [(v['video_id'], v['caption']) for v in uncategorized]
        ai_categories = categorize_by_ai(captions_with_ids)
        if ai_categories:
            update_categories_batch(ai_categories)
            print(f"[✓] Đã gắn mác AI cho {len(ai_categories)} video.")
    else:
        print("[✓] Tất cả video đã có danh mục.")

    # Chạy các bước hậu xử lý
    _run_post_processing()

    print(f"\n✅ AI CORE HOÀN TẤT! Đã xử lý {len(new_videos)} video mới.")


def _run_post_processing():
    """Các bước hậu xử lý luôn chạy dù có video mới hay không."""

    # 8. Tải video viral + dọn dẹp video cũ
    try:
        from video_downloader import download_viral_videos, cleanup_old_videos
        download_viral_videos()
        cleanup_old_videos()
    except ImportError:
        print("[!] Thiếu yt-dlp, bỏ qua bước tải video.")
    except Exception as e:
        print(f"[!] Lỗi khi tải/dọn video: {e}")

    # 9. Multimodal AI — Phân tích nội dung video toàn diện
    try:
        from multimodal_engine import run_multimodal_analysis
        run_multimodal_analysis()
    except ImportError as e:
        print(f"[!] Thiếu thư viện Multimodal AI (whisper/easyocr/moviepy), bỏ qua: {e}")
    except Exception as e:
        print(f"[!] Lỗi khi chạy Multimodal AI: {e}")

    # 9.5. ÉP BUỘC phân loại lại video "🌍 Khác" — CLIP + Ollama
    try:
        force_reclassify_khac_videos()
    except Exception as e:
        print(f"[!] Lỗi khi ép phân loại video Khác: {e}")

    # 10. Smart Keywords — NER + POS-tag cho Top 20 viral
    try:
        refresh_smart_keywords_for_top_viral(top_n=20)
    except Exception as e:
        print(f"[!] Lỗi khi cập nhật smart keywords: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='TrendSense AI Core Pipeline')
    parser.add_argument('--all', action='store_true', help='Duyệt lại toàn bộ dữ liệu từ đầu')
    args = parser.parse_args()
    
    process_new_videos(force_all=args.all)