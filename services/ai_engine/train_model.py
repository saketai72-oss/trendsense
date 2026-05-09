"""
Script huấn luyện model dự báo viral — chạy riêng mỗi tuần (Sunday midnight).
Sử dụng Sliding Window: chỉ train trên data N ngày gần nhất.

Cách dùng:
    python src/ai_core/train_model.py
"""
import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings

# Import database
from core.db.models import init_db, get_recent_videos

# Import model manager
from services.ai_engine.model_manager import save_model, get_model_info

FEATURES = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']


def train():
    print("\n" + "=" * 60)
    print("[*] KHỞI ĐỘNG LUỒNG HUẤN LUYỆN SONG SONG (DUAL MODEL)")
    print(f"   Sliding Window: {settings.SLIDING_WINDOW_DAYS} ngày gần nhất")
    print("=" * 60)

    # 1. Khởi tạo DB và lấy data
    init_db()
    rows = get_recent_videos(days=settings.SLIDING_WINDOW_DAYS)

    if not rows:
        print("[!] Không có dữ liệu. Huỷ training.")
        return

    df = pd.DataFrame(rows)
    print(f"[*] Đã load {len(df)} video.")

    # Lấy benchmark trend hiện tại để "dạy" Model B cách nhận biết trend
    from core.db.models import get_trending_keywords, get_trending_categories
    trending_kws = [k["keyword"].lower() for k in get_trending_keywords(days=7)]
    trending_cats = [c["category"] for c in get_trending_categories(days=7)]

    # 2. Feature Engineering
    # Features cho Model A (Dành cho video đã cào - Dựa trên tương tác)
    FEATURES_A = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']
    
    # Features cho Model B (Dành cho video Upload - Dựa trên nội dung & trend)
    def calculate_trend_score(row):
        score = 0
        kws = str(row.get('top_keywords', '')).lower()
        for tk in trending_kws[:20]:
            if tk in kws: score += 1
        cats = row.get('category', [])
        if cats and any(c in trending_cats[:5] for c in cats): score += 5
        return score

    df['Trend_Score'] = df.apply(calculate_trend_score, axis=1)
    df['Like_Rate'] = df['likes'] / df['views']
    df['Comment_Rate'] = df['comments'] / df['views']
    df['Share_Rate'] = df['shares'] / df['views']
    df['Save_Rate'] = df['saves'] / df['views']
    df['Positive_Score'] = df['positive_score'].fillna(0)
    df['Views_Per_Hour'] = df['views_per_hour'].fillna(0)
    df['Duration'] = df['video_duration'].fillna(0)
    df['Cuts_Per_Sec'] = df['scene_cut_count'].fillna(0) / df['Duration'].replace(0, 1)
    df['Is_Portrait'] = (df['video_orientation'] == 'portrait').astype(int)

    FEATURES_B = ['Trend_Score', 'Duration', 'Cuts_Per_Sec', 'Is_Portrait', 'Positive_Score']

    df.replace([np.inf, -np.inf], 0, inplace=True)
    df.fillna(0, inplace=True)

    # 3. Gắn nhãn mục tiêu
    vv = df['viral_velocity'].fillna(0)
    threshold = vv.quantile(0.80)
    if threshold <= 0: threshold = 0.001
    df['Is_Future_Trend'] = (vv >= threshold).astype(int)

    # 4. HUẤN LUYỆN MODEL A (Engagement Model)
    print("\n[🎓] Huấn luyện Model A (Dự đoán Viral cho Video đã cào)...")
    X_a = df[FEATURES_A]
    y = df['Is_Future_Trend']
    model_a = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    model_a.fit(X_a, y)
    save_model(model_a, {"accuracy": "N/A", "features": FEATURES_A}, name="rf_model")

    metrics = {"training_samples": len(df), "window_days": settings.SLIDING_WINDOW_DAYS}

    # 5. HUẤN LUYỆN MODEL B (Alignment Model - Uploads)
    print("[🎓] Huấn luyện Model B (Đánh giá Trend cho Video Upload)...")
    X_b = df[FEATURES_B]
    model_b = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42, class_weight='balanced')
    model_b.fit(X_b, y)
    save_model(model_b, {**metrics, "features": FEATURES_B}, name="alignment_model")

    # 6. Cập nhật kết quả dự đoán của Model A cho Video đã cào
    print("\n[*] Đang cập nhật Viral Probability (Model A) vào Database...")
    from core.db.models import get_connection
    probs = model_a.predict_proba(X_a)[:, 1]
    df['prob'] = [round(float(p) * 100, 1) for p in probs]

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute("UPDATE videos SET viral_probability = %s WHERE video_id = %s", (row['prob'], row['video_id']))
        conn.commit()
    finally:
        conn.close()

    print(f"\n{'=' * 60}\n[V] ĐÃ HUẤN LUYỆN XONG 2 MODEL & KẾT QUẢ DỰ ĐOÁN!\n{'=' * 60}")


if __name__ == "__main__":
    train()
