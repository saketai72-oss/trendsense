"""
Script huấn luyện model dự báo viral — chạy định kỳ (weekly).
Cải tiến: cross-validation, nhiều metrics, lưu feature importances, tích hợp trend analyzer.
"""
import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings
from core.db.models import get_recent_videos, get_connection
from services.ai_engine.model_manager import save_model
from services.ai_engine.trend_analyzer import run_trend_analysis

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

    # ---- Cross-validation (k=5) ----
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model = RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42)

    try:
        cv_acc = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
        cv_precision = cross_val_score(model, X, y, cv=cv, scoring='precision')
        cv_recall = cross_val_score(model, X, y, cv=cv, scoring='recall')
        cv_f1 = cross_val_score(model, X, y, cv=cv, scoring='f1')
        cv_auc = cross_val_score(model, X, y, cv=cv, scoring='roc_auc')
    except Exception as e:
        print(f"[!] Lỗi khi tính cross-validation: {e}")
        cv_acc = cv_precision = cv_recall = cv_f1 = cv_auc = np.array([0.0])

    print(f"[✓] CV Accuracy  : {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
    print(f"[✓] CV Precision : {cv_precision.mean():.4f} ± {cv_precision.std():.4f}")
    print(f"[✓] CV Recall    : {cv_recall.mean():.4f} ± {cv_recall.std():.4f}")
    print(f"[✓] CV F1        : {cv_f1.mean():.4f} ± {cv_f1.std():.4f}")
    print(f"[✓] CV AUC       : {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")

    # Train final model on all data
    model.fit(X, y)

    # Feature importances
    importances = dict(zip(FEATURES, model.feature_importances_))
    print("\nFeature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: x[1], reverse=True):
        print(f"  {feat}: {imp:.4f}")

    # Lưu model + metrics
    metrics = {
        "accuracy": cv_acc.mean(),
        "precision": cv_precision.mean(),
        "recall": cv_recall.mean(),
        "f1": cv_f1.mean(),
        "auc": cv_auc.mean(),
        "feature_importances": importances,
        "samples": len(df),
        "positive_ratio": y.mean(),
        "threshold_viral_velocity": threshold
    }
    save_model(model, metrics, name="rf_model")
    print("[✓] Đã lưu model và metrics vào data/models/")

    # Cập nhật viral_probability cho video hiện có
    print("[*] Đang cập nhật viral_probability vào database...")
    probs = model.predict_proba(X)[:, 1]
    df['viral_probability'] = (probs * 100).round(2).clip(0, 99.9)

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

    # ---- Gọi Model 2: Trend Analyzer ----
    run_trend_analysis(threshold_prob=70.0, days=settings.SLIDING_WINDOW_DAYS)

    print("\n" + "=" * 60 + "\n[✓] HUẤN LUYỆN HOÀN TẤT & TREND REPORT GENERATED!\n" + "=" * 60)

if __name__ == "__main__":
    train()
