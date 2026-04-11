"""
Categorizer — Phân loại video TikTok vào 12 danh mục (Multi-Label).
Hybrid: Rule-based nhanh cho 80% video, Zero-shot AI cho 20% còn lại.
Model: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli (nhẹ, đa ngữ).

Multi-Label: Mỗi video thuộc ít nhất 1 và tối đa MAX_CATEGORIES danh mục.
Lưu trữ: Nối bằng CATEGORY_SEPARATOR ("|"), ví dụ: "🍳 Ẩm thực|📚 Giáo dục"
"""
import re
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# =====================================================
# 12 DANH MỤC + BỘ TỪ KHOÁ TRIGGER
# =====================================================
CATEGORIES = {
    "🎭 Giải trí": [
        "funny", "hài", "comedy", "prank", "challenge", "viral", "trend",
        "hàihước", "troll", "reaction", "meme", "funnyvideo", "humor",
        "joke", "laugh", "lol", "skit", "parody", "giaitri", "cuoi"
    ],
    "🎵 Âm nhạc": [
        "music", "nhạc", "dance", "cover", "sing", "song", "remix",
        "nhảy", "choreography", "dj", "rap", "hiphop", "kpop", "vpop",
        "edm", "acoustic", "karaoke", "beat", "melody", "nhachay"
    ],
    "🍳 Ẩm thực": [
        "food", "nấu", "ăn", "cooking", "recipe", "amthuc", "mukbang",
        "nauan", "monngon", "bếp", "chef", "foodie", "doanay", "angi",
        "ngon", "review_food", "streetfood", "banhmi", "pho", "comtam"
    ],
    "💻 Công nghệ": [
        "tech", "review", "unbox", "congnghe", "iphone", "samsung", "laptop",
        "android", "ios", "app", "software", "coding", "programming", "gadget",
        "phone", "xiaomi", "oppo", "macbook", "pc", "gaming", "setup"
    ],
    "👗 Thời trang": [
        "fashion", "ootd", "outfit", "style", "thoitrang", "phoido",
        "dress", "clothes", "streetwear", "lookbook", "zara", "shein",
        "vintage", "aesthetic", "grwm", "getready", "deptrai", "xinh"
    ],
    "📚 Giáo dục": [
        "learn", "study", "tips", "hoc", "giaoduc", "knowledge", "howto",
        "tutorial", "hack", "diy", "lifehack", "explain", "science",
        "english", "tienganh", "math", "skill", "hoctap", "kienthuc"
    ],
    "🏋️ Thể thao": [
        "sport", "gym", "fitness", "football", "bóng", "workout", "soccer",
        "basketball", "boxing", "mma", "yoga", "run", "exercise", "thethai",
        "bongda", "nba", "epl", "worldcup", "olympic", "muscle"
    ],
    "🐾 Động vật": [
        "pet", "dog", "cat", "animal", "mèo", "chó", "cute",
        "puppy", "kitten", "bird", "fish", "hamster", "rabbit", "lion",
        "wildlife", "thucung", "dongvat", "bosuu", "zoo"
    ],
    "💄 Làm đẹp": [
        "beauty", "makeup", "skincare", "lamdep", "glow", "routine",
        "cosmetic", "lipstick", "foundation", "serum", "mask", "facial",
        "acne", "mun", "trang", "son", "phan", "kem", "duong"
    ],
    "📰 Tin tức": [
        "news", "drama", "tintuc", "sukien", "breakingnews", "trending",
        "xahoi", "drama_tiktoker", "expose", "scandal", "cap_nhat",
        "vietnam", "thoisu", "nong", "controversy", "beef", "exposed"
    ],
    "💰 Tài chính": [
        "finance", "taichinh", "crypto", "bitcoin", "kinhdoanh", "business",
        "money", "invest", "stock", "chungkhoan", "forex", "kiemtien",
        "startup", "entrepreneur", "passive_income", "trading", "nft",
        "income", "rich", "lamgiau"
    ],
}

# Label cho zero-shot (tiếng Anh để model hiểu tốt hơn)
ZERO_SHOT_LABELS = [
    "entertainment and comedy",
    "music and dance",
    "food and cooking",
    "technology and gadgets",
    "fashion and style",
    "education and learning",
    "sports and fitness",
    "animals and pets",
    "beauty and makeup",
    "news and current events",
    "finance and business",
]

# Map zero-shot label → emoji label
ZERO_SHOT_TO_CATEGORY = {
    "entertainment and comedy": "🎭 Giải trí",
    "music and dance": "🎵 Âm nhạc",
    "food and cooking": "🍳 Ẩm thực",
    "technology and gadgets": "💻 Công nghệ",
    "fashion and style": "👗 Thời trang",
    "education and learning": "📚 Giáo dục",
    "sports and fitness": "🏋️ Thể thao",
    "animals and pets": "🐾 Động vật",
    "beauty and makeup": "💄 Làm đẹp",
    "news and current events": "📰 Tin tức",
    "finance and business": "💰 Tài chính",
}


def extract_hashtags(caption):
    """Trích xuất hashtag từ caption, loại bỏ dấu # và chuyển thành lowercase"""
    if not caption or not isinstance(caption, str):
        return []
    # Tìm tất cả #tag, bao gồm cả tiếng Việt
    tags = re.findall(r'#(\w+)', caption.lower())
    return tags


def _join_categories(categories_list):
    """Nối danh sách danh mục thành chuỗi dùng separator từ settings"""
    if not categories_list:
        return "🌍 Khác"
    return settings.CATEGORY_SEPARATOR.join(categories_list)


def _split_categories(categories_str):
    """Tách chuỗi danh mục thành list"""
    if not categories_str or categories_str == "🌍 Khác":
        return []
    return [c.strip() for c in categories_str.split(settings.CATEGORY_SEPARATOR) if c.strip()]


def categorize_by_rules(caption):
    """
    Gắn mác nhanh bằng luật từ khoá (MULTI-LABEL).
    Phân tích cả hashtag lẫn nội dung caption.
    Trả về list danh mục có score >= RULE_MIN_SCORE, tối đa MAX_CATEGORIES.
    """
    if not caption:
        return []

    # Gộp hashtag + caption thành 1 chuỗi searchable
    text_lower = caption.lower()
    hashtags = extract_hashtags(caption)
    all_tokens = set(hashtags + text_lower.split())

    scored_categories = []

    for category, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in all_tokens)
        # Bonus: check cả substring (ví dụ "foodreview" chứa "food")
        for kw in keywords:
            if kw in text_lower and kw not in all_tokens:
                score += 0.5
        if score >= settings.RULE_MIN_SCORE:
            scored_categories.append((category, score))

    # Sắp xếp theo score giảm dần, lấy tối đa MAX_CATEGORIES
    scored_categories.sort(key=lambda x: x[1], reverse=True)
    return [cat for cat, _ in scored_categories[:settings.MAX_CATEGORIES]]


def categorize_by_ai(captions_with_ids):
    """
    Fallback: Dùng mDeBERTa zero-shot cho video không match rule (MULTI-LABEL).
    Input: list of (video_id, caption)
    Output: list of (category_string, video_id) sẵn sàng cho batch update
            category_string dùng CATEGORY_SEPARATOR nối nhiều danh mục
    """
    if not captions_with_ids:
        return []

    try:
        from transformers import pipeline

        print(f"[*] Đang tải model zero-shot: {settings.ZERO_SHOT_MODEL}...")
        classifier = pipeline(
            "zero-shot-classification",
            model=settings.ZERO_SHOT_MODEL,
            device=-1  # CPU (an toàn cho GitHub Actions)
        )
        print(f"[✓] Model zero-shot sẵn sàng.")

        results = []
        for i, (video_id, caption) in enumerate(captions_with_ids):
            if not caption or len(str(caption).strip()) < 5:
                # Caption quá ngắn → vẫn cố phân loại, KHÔNG GÁN "Khác"
                # Dùng video_id làm placeholder text
                caption = str(caption) if caption else "video"

            try:
                # Cắt caption max 200 ký tự để tăng tốc
                text = str(caption)[:200]
                res = classifier(text, ZERO_SHOT_LABELS, multi_label=True)

                # Lấy tất cả label có confidence >= threshold
                matched_labels = []
                for label, score in zip(res['labels'], res['scores']):
                    if score >= settings.ZERO_SHOT_THRESHOLD:
                        category = ZERO_SHOT_TO_CATEGORY.get(label)
                        if category:
                            matched_labels.append(category)
                    if len(matched_labels) >= settings.MAX_CATEGORIES:
                        break

                # NẾU không label nào vượt ngưỡng → CƯỠNG BỨC lấy top-1
                # TUYỆT ĐỐI KHÔNG trả về "🌍 Khác"
                if not matched_labels:
                    top_label = res['labels'][0]  # Label có score cao nhất
                    top_category = ZERO_SHOT_TO_CATEGORY.get(top_label)
                    if top_category:
                        matched_labels.append(top_category)
                        print(f"    [⚡] Force-classify {video_id}: {top_category} (score={res['scores'][0]:.2f})")

                category_str = _join_categories(matched_labels)
                results.append((category_str, video_id))

                if (i + 1) % 10 == 0:
                    print(f"  [AI] Đã phân loại {i+1}/{len(captions_with_ids)} video...")

            except Exception as e:
                print(f"  [!] Lỗi AI phân loại {video_id}: {e}")
                # Lỗi → gán danh mục phổ biến nhất thay vì "Khác"
                results.append(("🎭 Giải trí", video_id))

        return results

    except ImportError:
        print("[!] Thiếu thư viện transformers, bỏ qua zero-shot.")
        return [("🎭 Giải trí", vid) for vid, _ in captions_with_ids]
    except Exception as e:
        print(f"[!] Lỗi tải model zero-shot: {e}")
        return [("🎭 Giải trí", vid) for vid, _ in captions_with_ids]


def categorize_video(video_id, caption):
    """
    Phân loại 1 video bằng rule-based MULTI-LABEL (gọi ngay khi cào).
    Nhanh, không cần model AI.
    Trả về chuỗi "A|B|C" hoặc "🌍 Khác" nếu không match.
    """
    categories = categorize_by_rules(caption)
    return _join_categories(categories)
