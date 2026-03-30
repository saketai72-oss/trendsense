from transformers import pipeline

print("[*] Đang tải mô hình NLP (bert-base-multilingual)...")
nlp_model = pipeline("sentiment-analysis", model="nlptown/bert-base-multilingual-uncased-sentiment", device=-1)

def analyze_batch(comments_list):
    if not comments_list: return []
    return nlp_model(comments_list, batch_size=32, truncation=True)