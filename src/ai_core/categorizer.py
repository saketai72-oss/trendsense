"""
Categorizer — Phân loại video TikTok vào 12 danh mục.
Hybrid: Rule-based nhanh cho 80% video, Zero-shot AI cho 20% còn lại.
Model: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli (nhẹ, đa ngữ).
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


def categorize_by_rules(caption):
    """
    Gắn mác nhanh bằng luật từ khoá.
    Phân tích cả hashtag lẫn nội dung caption.
    Trả về danh mục hoặc None nếu không match.
    """
    if not caption:
        return None

    # Gộp hashtag + caption thành 1 chuỗi searchable
    text_lower = caption.lower()
    hashtags = extract_hashtags(caption)
    all_tokens = set(hashtags + text_lower.split())

    best_category = None
    best_score = 0

    for category, keywords in CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in all_tokens)
        # Bonus: check cả substring (ví dụ "foodreview" chứa "food")
        for kw in keywords:
            if kw in text_lower and kw not in all_tokens:
                score += 0.5
        if score > best_score:
            best_score = score
            best_category = category

    # Chỉ trả về nếu match tối thiểu 1 từ khoá
    if best_score >= 1:
        return best_category
    return None


def categorize_by_ai(captions_with_ids):
    """
    Fallback: Dùng mDeBERTa zero-shot cho video không match rule.
    Input: list of (video_id, caption)
    Output: list of (category, video_id) sẵn sàng cho batch update
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
                results.append(("🌍 Khác", video_id))
                continue

            try:
                # Cắt caption max 200 ký tự để tăng tốc
                text = str(caption)[:200]
                res = classifier(text, ZERO_SHOT_LABELS, multi_label=False)
                top_label = res['labels'][0]
                confidence = res['scores'][0]

                if confidence >= 0.3:
                    category = ZERO_SHOT_TO_CATEGORY.get(top_label, "🌍 Khác")
                else:
                    category = "🌍 Khác"

                results.append((category, video_id))

                if (i + 1) % 10 == 0:
                    print(f"  [AI] Đã phân loại {i+1}/{len(captions_with_ids)} video...")

            except Exception as e:
                print(f"  [!] Lỗi AI phân loại {video_id}: {e}")
                results.append(("🌍 Khác", video_id))

        return results

    except ImportError:
        print("[!] Thiếu thư viện transformers, bỏ qua zero-shot.")
        return [("🌍 Khác", vid) for vid, _ in captions_with_ids]
    except Exception as e:
        print(f"[!] Lỗi tải model zero-shot: {e}")
        return [("🌍 Khác", vid) for vid, _ in captions_with_ids]


def categorize_video(video_id, caption):
    """
    Phân loại 1 video bằng rule-based (gọi ngay khi cào).
    Nhanh, không cần model AI.
    """
    category = categorize_by_rules(caption)
    return category if category else "🌍 Khác"
