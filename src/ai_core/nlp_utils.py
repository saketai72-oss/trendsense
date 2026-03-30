import re
import pandas as pd
from underthesea import word_tokenize

STOPWORDS = {
    "và", "là", "của", "có", "trong", "với", "cho", "không", "những", "một", "các", 
    "khi", "để", "mà", "thì", "được", "này", "người", "tôi", "bạn", "nó", "thế", 
    "nào", "đã", "từ", "rất", "quá", "hay", "gì", "cũng", "nan", "the", "to", "a", 
    "is", "of", "it", "in", "for",
    "có_thể", "như_vậy", "thế_nào", "tuy_nhiên", "bây_giờ", "thực_sự", "chắc_chắn", 
    "như_thế", "đang", "nhưng", "rằng", "nên", "lại", "thấy", "đi", "nhiều", "biết"
}

def clean_text(text):
    if not isinstance(text, str) or pd.isna(text): return ""
    text = text.lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text)
    return text.strip()

def extract_keywords(txt):
    if not txt: return []
    tokenized_txt = word_tokenize(txt, format="text")
    return [w for w in tokenized_txt.split() if len(w) > 2 and w.lower() not in STOPWORDS]