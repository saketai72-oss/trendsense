"""
NLP Utils — Tiền xử lý văn bản và trích xuất từ khóa.
- extract_keywords(): Lọc stopword cơ bản (nhanh, cho video thường)
- extract_smart_keywords(): Dùng NER + POS-tag underthesea (chậm hơn, cho top viral)
  → Chỉ giữ: tên riêng, địa danh, thương hiệu, sản phẩm
  → Loại bỏ: động từ, tính từ, đại từ vô nghĩa
"""
import re
import pandas as pd
from underthesea import word_tokenize

# =====================================================
# STOPWORDS MỞ RỘNG: bao gồm cả động từ tiếng Việt phổ biến
# =====================================================
STOPWORDS = {
    # --- Liên từ, giới từ, đại từ cơ bản ---
    "và", "là", "của", "có", "trong", "với", "cho", "không", "những", "một", "các",
    "khi", "để", "mà", "thì", "được", "này", "người", "tôi", "bạn", "nó", "thế",
    "nào", "đã", "từ", "rất", "quá", "hay", "gì", "cũng", "nan", "đều", "vẫn",
    "sẽ", "phải", "luôn", "như", "nếu", "vì", "tại", "đó", "đây", "kia", "ấy",
    "hết", "mọi", "nữa", "chưa", "bao", "bởi", "mỗi", "đến", "theo", "trên",
    "dưới", "trước", "sau", "giữa", "ngoài", "chỉ", "về", "ra", "lên", "xuống",

    # --- Động từ phổ biến VÔ NGHĨA khi làm keyword ---
    "muốn", "thích", "xem", "làm", "nên", "bảo", "nghĩ", "nói", "hiểu",
    "biết", "thấy", "đang", "nhưng", "rằng", "lại", "đi", "nhiều",
    "có_thể", "như_vậy", "thế_nào", "tuy_nhiên", "bây_giờ", "thực_sự",
    "chắc_chắn", "như_thế", "chứ", "ơi", "nhé", "nha", "ạ", "hả",
    "cần", "phải", "nên", "hãy", "đừng", "chớ", "bị", "cho", "lấy",
    "mua", "bán", "đưa", "đặt", "gửi", "nhận", "mở", "đóng", "chạy",
    "ngồi", "đứng", "nằm", "ở", "sống", "chết", "yêu", "ghét", "sợ",
    "giúp", "dùng", "tìm", "gọi", "hỏi", "trả_lời", "viết", "đọc",
    "nghe", "nhìn", "cảm_thấy", "tin", "tưởng", "chia_sẻ", "follow",
    "subscribe", "like", "share", "comment", "save", "duet", "stitch",

    # --- Tính từ phổ biến VÔ NGHĨA khi làm keyword ---
    "đẹp", "xấu", "tốt", "giỏi", "dở", "hay", "buồn", "vui", "sến",
    "lớn", "nhỏ", "dài", "ngắn", "cao", "thấp", "nhanh", "chậm",
    "mới", "cũ", "trẻ", "già", "khó", "dễ", "đúng", "sai",

    # --- Từ media/TikTok noise ---
    "video", "clip", "fyp", "tiktok", "foryou", "trending", "trend",
    "review", "unbox", "pro", "max", "mini", "phần", "tập", "số",

    # --- Compound verbs (underthesea tokenize thành 1 từ) ---
    "lam_hieu", "nghi_noi", "can_phai", "can_phai_nen", "nhu_the",
    "the_nao", "nhu_vay", "chia_se", "tra_loi", "cam_thay",
    "an_o", "di_an", "lam_gi", "nhu_nao",

    # --- Phó từ ---
    "rất", "quá", "lắm", "cực", "siêu", "hơi", "khá", "tương_đối",
    "hoàn_toàn", "gần_như", "thêm", "còn", "đã", "sẽ", "đang",

    # --- Từ tiếng Anh phổ biến trong comment TikTok ---
    "the", "to", "a", "is", "of", "it", "in", "for", "que", "this",
    "that", "you", "like", "was", "what", "who", "not", "one", "how",
    "are", "first", "they", "sticker", "with", "and", "but", "so",
    "very", "thank", "thanks", "please", "yes", "no", "omg", "lol",
    "haha", "wow", "really", "just", "want", "love", "hate", "best",
    "good", "bad", "nice", "cool", "cute", "hot", "viral",

    # --- Biến thể KHÔNG DẤU (comment TikTok thường không gõ dấu) ---
    "muon", "thich", "lam", "biet", "thay", "duoc", "nguoi", "nhung",
    "cung", "nhieu", "khong", "dang", "noi", "nghi", "hieu", "bao",
    "can", "phai", "nen", "hay", "dung", "cho", "den", "nay", "day",
    "rat", "qua", "lam", "cuc", "sieu", "hoi", "dep", "xau", "tot",
    "gioi", "buon", "vui", "moi", "cu", "tre", "gia", "kho", "de",
    "dung", "sai", "lon", "nho", "dai", "ngan", "cao", "thap",
    "nhanh", "cham", "yeu", "ghet", "so", "tin", "tuong",
    "toi", "ban", "no", "minh", "anh", "chi", "em", "con", "cha",
    "me", "ba", "ong", "co",
}


def clean_text(text):
    """Làm sạch text: lowercase, bỏ URL, bỏ ký tự đặc biệt (giữ tiếng Việt)"""
    if not isinstance(text, str) or pd.isna(text): return ""
    text = text.lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text)
    return text.strip()


def extract_keywords(txt):
    """
    Trích xuất từ khóa CƠ BẢN (nhanh, dùng cho video thường).
    Chỉ lọc stopword, không cần NER/POS-tag.
    """
    if not txt: return []
    tokenized_txt = word_tokenize(txt, format="text")
    return [w for w in tokenized_txt.split() if len(w) > 2 and w.lower() not in STOPWORDS]


def extract_smart_keywords(txt):
    """
    Trích xuất từ khóa loại bỏ các verb và noise.
    Đã lược bỏ NER do thiếu ổn định và tạo ra từ khóa lỗi.
    Sử dụng word_tokenize kết hợp với danh sách STOPWORDS mở rộng.
    """
    if not txt or len(txt.strip()) < 5:
        return []

    try:
        keywords = extract_keywords(txt)
        return [kw.replace("_", " ") for kw in keywords]

    except Exception:
        return []