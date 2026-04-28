import os
from core.config.base import *

# Service-Specific Paths
SERVICES_DIR = os.path.join(BASE_DIR, 'services')

# Web Scraper Config
EDGE_PROFILE_DIR = os.path.join(DATA_DIR, 'edge_profile')
# Changed to point strictly to new service location if needed
DRIVER_PATH = os.path.join(SERVICES_DIR, 'tiktok-scraper', 'msedgedriver.exe')

# AI Core / Models Config
MODEL_DIR = os.path.join(DATA_DIR, 'models')
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, 'rf_model.joblib')
METRICS_PATH = os.path.join(MODEL_DIR, 'metrics.json')

# Video Download Config
VIDEOS_DIR = os.path.join(DATA_DIR, 'videos')
os.makedirs(VIDEOS_DIR, exist_ok=True)

MAX_VIDEOS = 1
SLIDING_WINDOW_DAYS = 14

DOWNLOAD_VIDEOS = True
DOWNLOAD_VIRAL_ONLY = False
VIRAL_DOWNLOAD_THRESHOLD = 50
VIDEO_RETENTION_DAYS = 14
MAX_VIDEO_SIZE_MB = 15
MAX_VIDEO_DURATION = 180
VIDEO_FORMAT = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

# AI / Multimodal Engine Config
ZERO_SHOT_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
CATEGORY_SEPARATOR = "|"
MAX_CATEGORIES = 3
RULE_MIN_SCORE = 1
ZERO_SHOT_THRESHOLD = 0.3

VISION_CAPTION_MODEL = "Salesforce/blip-image-captioning-base"
VISION_CLIP_MODEL = "openai/clip-vit-base-patch32"
VISION_KEYFRAMES = 4
VISION_CATEGORY_OVERRIDE_THRESHOLD = 0.6

WHISPER_MODEL = "base"
WHISPER_COMPUTE_TYPE = "int8"

OCR_LANG = ['vi', 'en']
OCR_FRAMES = 2

OLLAMA_MODEL = "llama3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"
