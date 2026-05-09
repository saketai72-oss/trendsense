"""
Quản lý việc lưu/tải model AI đã huấn luyện.
Model được lưu dưới dạng .joblib kèm metadata JSON.
"""
import joblib
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings


def save_model(model, metrics_dict, name="rf_model"):
    """Lưu model và metadata kèm theo"""
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    path = os.path.join(settings.MODEL_DIR, f"{name}.joblib")
    metrics_path = os.path.join(settings.MODEL_DIR, f"{name}_metrics.json")

    # Lưu model
    joblib.dump(model, path)

    # Lưu metadata
    meta = {
        **metrics_dict,
        "trained_at": datetime.now().isoformat(),
        "model_file": os.path.basename(path),
    }
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[✓] Model đã lưu tại: {path}")


def load_model(name="rf_model"):
    """Load model theo tên. Trả về None nếu chưa có."""
    path = os.path.join(settings.MODEL_DIR, f"{name}.joblib")
    if not os.path.exists(path):
        return None

    model = joblib.load(path)
    return model


def get_model_info(name="rf_model"):
    """Đọc metadata của model theo tên."""
    path = os.path.join(settings.MODEL_DIR, f"{name}_metrics.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None
