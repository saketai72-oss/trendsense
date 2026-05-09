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

    # 2. Feature Engineering & Data Cleaning
    df['Like_Rate'] = df['likes'] / df['views'].replace(0, 1)
    df['Comment_Rate'] = df['comments'] / df['views'].replace(0, 1)
    df['Share_Rate'] = df['shares'] / df['views'].replace(0, 1)
    df['Save_Rate'] = df['saves'] / df['views'].replace(0, 1)
    df['Positive_Score'] = pd.to_numeric(df['positive_score'], errors='coerce').fillna(50)
    df['Views_Per_Hour'] = pd.to_numeric(df['views_per_hour'], errors='coerce').fillna(0)
    df['Duration'] = pd.to_numeric(df['video_duration'], errors='coerce').fillna(0)
    df['Cuts_Per_Sec'] = pd.to_numeric(df['scene_cut_count'], errors='coerce').fillna(0) / df['Duration'].replace(0, 1)
    
    # Advanced Features cho Model B
    def get_keyword_count(row):
        kws = str(row.get('top_keywords', '')).lower()
        return sum(1 for tk in trending_kws[:30] if tk in kws)

    df['KW_Match_Count'] = df.apply(get_keyword_count, axis=1)
    
    # Category Hotness (0 to 5)
    trending_cats_top = trending_cats[:10]
    def get_cat_rank(row):
        cats = row.get('category', [])
        if isinstance(cats, str): cats = [cats]
        for i, c in enumerate(trending_cats_top):
            if cats and c in cats: return 10 - i
        return 0
    df['Cat_Hotness'] = df.apply(get_cat_rank, axis=1)

    # Duration Buckets (TikTok optimization)
    df['Is_Ideal_Duration'] = ((df['Duration'] >= 15) & (df['Duration'] <= 35)).astype(int)
    df['Is_Portrait'] = (df['video_orientation'] == 'portrait').astype(int)
    
    # Interaction: Trend + Sentiment
    df['Trend_Sentiment_Score'] = df['KW_Match_Count'] * (df['Positive_Score'] / 100.0)

    FEATURES_A = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']
    FEATURES_B = ['KW_Match_Count', 'Cat_Hotness', 'Duration', 'Cuts_Per_Sec', 'Is_Portrait', 'Is_Ideal_Duration', 'Trend_Sentiment_Score']

    from sklearn.ensemble import HistGradientBoostingClassifier
    
    # Clean data: Loại bỏ các dòng có quá nhiều giá trị 0 hoặc NaN
    df = df.replace([np.inf, -np.inf], 0).fillna(0)

    # 3. Gắn nhãn mục tiêu
    vv = df['viral_velocity'].fillna(0)
    threshold = vv.quantile(0.85) # Tăng độ khó để bắt được trend thực sự
    if threshold <= 0: threshold = 0.001
    df['Is_Future_Trend'] = (vv >= threshold).astype(int)

    # 4. HUẤN LUYỆN MODEL A (Engagement)
    print("\n[🎓] Huấn luyện Model A (Engagement Model)...")
    X_a = df[FEATURES_A]
    y = df['Is_Future_Trend']
    
    acc_a = "N/A"
    try:
        if len(df) >= 50:
            Xa_train, Xa_test, ya_train, ya_test = train_test_split(X_a, y, test_size=0.2, random_state=42, stratify=y)
            model_a = HistGradientBoostingClassifier(max_iter=200, random_state=42)
            model_a.fit(Xa_train, ya_train)
            acc_a = round(accuracy_score(ya_test, model_a.predict(Xa_test)), 4)
            model_a.fit(X_a, y)
        else:
            model_a = HistGradientBoostingClassifier(max_iter=100, random_state=42)
            model_a.fit(X_a, y)
    except Exception:
        model_a = RandomForestClassifier(n_estimators=100, random_state=42)
        model_a.fit(X_a, y)

    save_model(model_a, {"accuracy": acc_a, "features": FEATURES_A}, name="engagement_predictor")

    # 5. HUẤN LUYỆN MODEL B (Alignment - Siêu cấp)
    print("[🎓] Huấn luyện Model B (Advanced Alignment Model)...")
    X_b = df[FEATURES_B]
    
    acc_b = "N/A"
    try:
        if len(df) >= 50:
            Xb_train, Xb_test, yb_train, yb_test = train_test_split(X_b, y, test_size=0.2, random_state=42, stratify=y)
            # Dùng HistGradientBoosting cho độ chính xác cao hơn RF
            model_b = HistGradientBoostingClassifier(
                max_iter=300,
                max_depth=10,
                learning_rate=0.05,
                l2_regularization=0.1,
                random_state=42
            )
            model_b.fit(Xb_train, yb_train)
            acc_b = round(accuracy_score(yb_test, model_b.predict(Xb_test)), 4)
            model_b.fit(X_b, y)
        else:
            model_b = HistGradientBoostingClassifier(max_iter=100, random_state=42)
            model_b.fit(X_b, y)
    except Exception as e:
        print(f"    [!] Fallback to RF: {e}")
        model_b = RandomForestClassifier(n_estimators=100, random_state=42)
        model_b.fit(X_b, y)

    metrics = {"training_samples": len(df), "window_days": settings.SLIDING_WINDOW_DAYS}
    save_model(model_b, {**metrics, "accuracy": acc_b, "features": FEATURES_B}, name="trend_analyzer")

    # 6. Cập nhật kết quả dự đoán của Model A cho Video đã cào
    print("\n[*] Đang cập nhật Viral Probability (Engagement Predictor) vào Database...")
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
