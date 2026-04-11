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

    # ==========================================
    # CẬP NHẬT: Không cần dự đoán các video quá cũ
    # (Tạo cách đây hơn 2 tuần = 14 ngày = 1.209.600 giây)
    # ==========================================
    import time
    current_time = int(time.time())
    two_weeks_seconds = 14 * 24 * 60 * 60
    
    # Chia DataFrame ra làm 2 phần
    # - df_recent: Các video dưới 2 tuần tuổi (Cần chạy model AI dự báo)
    # - df_old: Các video cũ hơn 2 tuần (Bỏ qua dự báo, gán 0.0)
    if 'create_time' in df.columns:
        is_recent_mask = (current_time - df['create_time']) <= two_weeks_seconds
        df_recent = df[is_recent_mask].copy()
        df_old = df[~is_recent_mask].copy()
    else:
        df_recent = df.copy()
        df_old = pd.DataFrame()
        
    print(f"[*] Tìm thấy {len(df_recent)} video dưới 2 tuần để chạy dự báo.")
    if len(df_old) > 0:
        print(f"[*] Từ chối dự báo cho {len(df_old)} video (quá cũ, tự động gán 0%).")
        df_old['viral_probability'] = 0.0
    
    if len(df_recent) == 0:
        return pd.concat([df_recent, df_old]).sort_values(by='viral_probability', ascending=False) if len(df_old) > 0 else df

    # Từ đây trở xuống, chỉ feature engineering trên các video MỚI (df_recent)
    df_recent['Like_Rate'] = df_recent['likes'] / df_recent['views']
    df_recent['Comment_Rate'] = df_recent['comments'] / df_recent['views']
    df_recent['Share_Rate'] = df_recent['shares'] / df_recent['views']
    df_recent['Save_Rate'] = df_recent['saves'] / df_recent['views']
    df_recent['Positive_Score'] = df_recent['positive_score'].fillna(0)
    df_recent['Views_Per_Hour'] = df_recent['views_per_hour'].fillna(0)

    df_recent.replace([np.inf, -np.inf], 0, inplace=True)
    df_recent[FEATURES] = df_recent[FEATURES].fillna(0)

    # 3. Load model đã train sẵn
    model = load_model()
    if model is None:
        print("[!] ⚠️ Chưa có model. Gán xác suất mặc định 5.0%.")
        print("    → Chạy 'python src/ai_core/train_model.py' để tạo model.")
        df_recent['viral_probability'] = 5.0
        return pd.concat([df_recent, df_old])

    # 4. CHỈ PREDICT — Không train
    X = df_recent[FEATURES]
    try:
        probabilities = model.predict_proba(X)[:, 1]
        df_recent['viral_probability'] = np.round(probabilities * 100, 2)
        print(f"[✓] Đã predict xác suất viral cho {len(df_recent)} video.")
    except Exception as e:
        print(f"[!] Lỗi khi predict: {e}")
        print("    → Model có thể không tương thích. Chạy lại train_model.py.")
        df_recent['viral_probability'] = 5.0

    # 5. Dọn cột trung gian
    cols_to_drop = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate']
    df_recent = df_recent.drop(columns=[c for c in cols_to_drop if c in df_recent.columns])
    
    # Gộp lại với các video CŨ trước khi trả về
    df_final = pd.concat([df_recent, df_old])
    return df_final.sort_values(by='viral_probability', ascending=False)