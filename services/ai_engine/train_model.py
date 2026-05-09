"""
Script huấn luyện model dự báo viral — chạy định kỳ (weekly).
Chỉ dùng engagement features, không phụ thuộc vào cột đã xóa.
"""
import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings
from core.db.models import get_recent_videos, get_connection
from services.ai_engine.model_manager import save_model

FEATURES = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']

def train():
    print("\n" + "=" * 60)
    print("[*] KHỞI ĐỘNG HUẤN LUYỆN MODEL DỰ BÁO VIRAL")
    print(f"   Sliding Window: {settings.SLIDING_WINDOW_DAYS} ngày gần nhất")
    print("=" * 60)

    rows = get_recent_videos(days=settings.SLIDING_WINDOW_DAYS)
    if not rows:
        print("[!] Không có dữ liệu. Huỷ training.")
        return

    df = pd.DataFrame(rows)
    print(f"[*] Đã load {len(df)} video.")

    # Feature engineering
    df['Like_Rate'] = df['likes'] / df['views'].replace(0, 1)
    df['Comment_Rate'] = df['comments'] / df['views'].replace(0, 1)
    df['Share_Rate'] = df['shares'] / df['views'].replace(0, 1)
    df['Save_Rate'] = df['saves'] / df['views'].replace(0, 1)
    df['Positive_Score'] = pd.to_numeric(df['positive_score'], errors='coerce').fillna(50)
    df['Views_Per_Hour'] = pd.to_numeric(df['views_per_hour'], errors='coerce').fillna(0)

    df[FEATURES] = df[FEATURES].fillna(0).replace([np.inf, -np.inf], 0)

    # Nhãn: Top 85% viral_velocity
    vv = df['viral_velocity'].fillna(0)
    threshold = vv.quantile(0.85)
    if threshold <= 0:
        threshold = 0.001
    df['Is_Viral'] = (vv >= threshold).astype(int)

    X = df[FEATURES]
    y = df['Is_Viral']

    # Chia tập train/test nếu đủ dữ liệu
    if len(df) >= 50:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        model = RandomForestClassifier(
            n_estimators=100,
            class_weight='balanced',   # Giảm overconfidence
            random_state=42
        )
        model.fit(X_train, y_train)
        acc = accuracy_score(y_test, model.predict(X_test))
        print(f"[✓] Accuracy: {acc:.4f}")
        # Train lại trên toàn bộ dữ liệu
        model.fit(X, y)
    else:
        model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)
        model.fit(X, y)
        acc = None

    # Lưu model
    save_model(model, {"accuracy": acc, "features": FEATURES, "samples": len(df)}, name="rf_model")
    print("[✓] Đã lưu model vào data/models/rf_model.joblib")

    # Cập nhật viral_probability cho video hiện có
    print("[*] Đang cập nhật viral_probability vào database...")
    probs = model.predict_proba(X)[:, 1]
    df['viral_probability'] = np.round(probs * 100, 2).clip(0, 99.9) # type: ignore

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                cur.execute(
                    "UPDATE videos SET viral_probability = %s WHERE video_id = %s",
                    (row['viral_probability'], row['video_id'])
                )
        conn.commit()
        print(f"[✓] Đã cập nhật {len(df)} video.")
    finally:
        conn.close()

    print("\n" + "=" * 60 + "\n[✓] HUẤN LUYỆN HOÀN TẤT!\n" + "=" * 60)

if __name__ == "__main__":
    train()