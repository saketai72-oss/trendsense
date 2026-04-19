import os
from dotenv import load_dotenv

# Base Directory: root of the project (TrendSense)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

# Shared Database URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("FATAL: DATABASE_URL not found in .env! TrendSense requires a PostgreSQL database to run.")

DATA_DIR = os.path.join(BASE_DIR, 'data')

# Shared API Keys
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODAL_WEBHOOK_URL = os.getenv("MODAL_WEBHOOK_URL", "")
