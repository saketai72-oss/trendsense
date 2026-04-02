"""
Prediction Engine — Chế độ INFERENCE ONLY.
Load model đã train sẵn và chỉ predict, không train lại.
"""
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

from model_manager import load_model

FEATURES = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']


def run_viral_prediction(df):
    """Dự đoán xác suất viral — CHỈ INFERENCE, KHÔNG TRAIN."""
    print("\n[🚀] KHỞI ĐỘNG MÔ HÌNH DỰ BÁO (INFERENCE MODE)...")

    # 1. Lọc data hợp lệ
    df = df[df['views'] > 0].copy()

    if len(df) == 0:
        print("[!] Không có video hợp lệ để dự đoán.")
        return df

    # 2. Feature Engineering
    df['Like_Rate'] = df['likes'] / df['views']
    df['Comment_Rate'] = df['comments'] / df['views']
    df['Share_Rate'] = df['shares'] / df['views']
    df['Save_Rate'] = df['saves'] / df['views']
    df['Positive_Score'] = df['positive_score'].fillna(0)
    df['Views_Per_Hour'] = df['views_per_hour'].fillna(0)

    df.replace([np.inf, -np.inf], 0, inplace=True)
    df[FEATURES] = df[FEATURES].fillna(0)

    # 3. Load model đã train sẵn
    model = load_model()
    if model is None:
        print("[!] ⚠️ Chưa có model. Gán xác suất mặc định 5.0%.")
        print("    → Chạy 'python src/ai_core/train_model.py' để tạo model.")
        df['viral_probability'] = 5.0
        return df

    # 4. CHỈ PREDICT — Không train
    X = df[FEATURES]
    try:
        probabilities = model.predict_proba(X)[:, 1]
        df['viral_probability'] = np.round(probabilities * 100, 2)
        print(f"[✓] Đã predict xác suất viral cho {len(df)} video.")
    except Exception as e:
        print(f"[!] Lỗi khi predict: {e}")
        print("    → Model có thể không tương thích. Chạy lại train_model.py.")
        df['viral_probability'] = 5.0

    # 5. Dọn cột trung gian
    cols_to_drop = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate']
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    return df.sort_values(by='viral_probability', ascending=False)