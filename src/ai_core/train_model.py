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
from config import settings

# Import database từ scraper
sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
from database import init_db, get_recent_videos

# Import model manager
from model_manager import save_model, get_model_info

FEATURES = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']


def train():
    print("\n" + "=" * 60)
    print("🧠 KHỞI ĐỘNG LUỒNG TRAIN — WEEKLY RETRAIN")
    print(f"   Sliding Window: {settings.SLIDING_WINDOW_DAYS} ngày gần nhất")
    print("=" * 60)

    # 1. Khởi tạo DB và lấy data
    init_db()
    rows = get_recent_videos(days=settings.SLIDING_WINDOW_DAYS)

    if not rows:
        print("[!] ❌ Không có dữ liệu nào trong cửa sổ thời gian. Huỷ training.")
        return

    df = pd.DataFrame(rows)
    print(f"\n[*] Đã load {len(df)} video từ {settings.SLIDING_WINDOW_DAYS} ngày gần nhất.")

    # 2. Lọc data hợp lệ
    df = df[df['views'] > 0].copy()
    if len(df) < 5:
        print(f"[!] ⚠️ Dữ liệu quá ít ({len(df)} video). Cần ít nhất 5 video.")
        return

    # 3. Feature Engineering
    df['Like_Rate'] = df['likes'] / df['views']
    df['Comment_Rate'] = df['comments'] / df['views']
    df['Share_Rate'] = df['shares'] / df['views']
    df['Save_Rate'] = df['saves'] / df['views']
    df['Positive_Score'] = df['positive_score'].fillna(0)
    df['Views_Per_Hour'] = df['views_per_hour'].fillna(0)

    df.replace([np.inf, -np.inf], 0, inplace=True)
    df[FEATURES] = df[FEATURES].fillna(0)

    # 4. Gắn nhãn mục tiêu (dùng Viral Velocity)
    vv = df['viral_velocity'].fillna(0)
    threshold = vv.quantile(0.80)
    if threshold <= 0:
        threshold = 0.001

    df['Is_Future_Trend'] = (vv >= threshold).astype(int)

    if len(df['Is_Future_Trend'].unique()) < 2:
        print("[!] ⚠️ Dữ liệu chưa đủ độ phân hoá. Không thể train.")
        print("    → Cần thêm data để có cả video trend và video bình thường.")
        return

    # 5. Huấn luyện
    X = df[FEATURES]
    y = df['Is_Future_Trend']

    metrics = {"training_samples": len(X), "window_days": settings.SLIDING_WINDOW_DAYS}

    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print(f"\n[*] Training: {len(X_train)} mẫu | Testing: {len(X_test)} mẫu")

        rf_model = RandomForestClassifier(
            n_estimators=100, random_state=42, class_weight='balanced'
        )
        rf_model.fit(X_train, y_train)

        # Đánh giá
        y_pred = rf_model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        metrics["accuracy"] = round(acc, 4)

        if len(y_test.unique()) == 2:
            print("\n📊 BÁO CÁO ĐỘ CHÍNH XÁC (TESTING):")
            print(classification_report(
                y_test, y_pred,
                target_names=['Bình thường', 'SẼ THÀNH TREND'],
                zero_division=0
            ))
        print(f"[*] Accuracy: {acc:.2%}")

    except ValueError as e:
        print(f"[!] ⚠️ Không đủ data để split test ({e}). Train trên toàn bộ.")
        rf_model = RandomForestClassifier(
            n_estimators=100, random_state=42, class_weight='balanced'
        )
        rf_model.fit(X, y)
        metrics["accuracy"] = "trained_without_test"
        metrics["note"] = "Dataset too small for train/test split"

    # 6. Lưu model
    # So sánh với model cũ (nếu có)
    old_info = get_model_info()
    if old_info and isinstance(old_info.get('accuracy'), float):
        old_acc = old_info['accuracy']
        new_acc = metrics.get('accuracy', 0)
        if isinstance(new_acc, float) and new_acc < old_acc * 0.8:
            print(f"\n[!] ⚠️ CẢNH BÁO: Model mới ({new_acc:.2%}) tệ hơn model cũ ({old_acc:.2%}) > 20%!")
            print("    → Vẫn lưu model mới nhưng cần theo dõi.")

    save_model(rf_model, metrics)

    # 7. Feature importance
    print("\n🔍 ĐỘ QUAN TRỌNG CỦA CÁC FEATURES:")
    for feat, imp in sorted(zip(FEATURES, rf_model.feature_importances_), key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"   {feat:20s} {imp:.3f} {bar}")

    print(f"\n{'=' * 60}")
    print("✅ TRAINING HOÀN TẤT! Model đã sẵn sàng cho luồng Inference.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    train()
