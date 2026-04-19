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


def save_model(model, metrics_dict):
    """Lưu model đã train và metadata kèm theo"""
    os.makedirs(settings.MODEL_DIR, exist_ok=True)

    # Lưu model
    joblib.dump(model, settings.MODEL_PATH)

    # Lưu metadata
    meta = {
        **metrics_dict,
        "trained_at": datetime.now().isoformat(),
        "model_file": os.path.basename(settings.MODEL_PATH),
    }
    with open(settings.METRICS_PATH, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[✓] Model đã lưu tại: {settings.MODEL_PATH}")
    print(f"[✓] Metadata đã lưu tại: {settings.METRICS_PATH}")


def load_model():
    """Load model đã train sẵn. Trả về None nếu chưa có."""
    if not os.path.exists(settings.MODEL_PATH):
        print("[!] ⚠️ Chưa có model file. Cần chạy train_model.py trước!")
        return None

    model = joblib.load(settings.MODEL_PATH)
    info = get_model_info()
    if info:
        print(f"[✓] Đã load model (trained: {info.get('trained_at', 'N/A')}, "
              f"accuracy: {info.get('accuracy', 'N/A')}, "
              f"samples: {info.get('training_samples', 'N/A')})")
    return model


def get_model_info():
    """Đọc metadata của model hiện tại. None nếu chưa có."""
    if not os.path.exists(settings.METRICS_PATH):
        return None
    try:
        with open(settings.METRICS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
