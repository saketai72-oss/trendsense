"""
TrendSense — RQ Worker
=======================
Chạy worker này để xử lý các Gemini AI job trong hàng đợi Redis.

Khởi động:
    python -m backend.worker
    (hoặc) rq worker gemini_jobs --url $REDIS_URL

Worker sẽ:
- Kéo job từ queue "gemini_jobs"
- Tự động retry nếu Gemini trả 429 / 503 (xem retry config)
- Survive được FastAPI restart — job vẫn sống trong Redis

Retry schedule mặc định:
    Lần 1: sau 60 giây
    Lần 2: sau 180 giây (3 phút)
    Lần 3: sau 600 giây (10 phút)
"""
import os
import sys
import logging

# Đảm bảo project root trong sys.path khi chạy trực tiếp
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

from redis import Redis
from rq import Worker, Queue
from rq.timeouts import JobTimeoutException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("trendsense.worker")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
QUEUE_NAME = "gemini_jobs"

# Timeout cho mỗi job: 15 phút (tải video + Gemini polling + DB write)
JOB_TIMEOUT = 900


def main():
    logger.info(f"[Worker] Kết nối Redis: {REDIS_URL}")
    try:
        conn = Redis.from_url(REDIS_URL)
        conn.ping()
        logger.info("[Worker] ✅ Redis connected")
    except Exception as e:
        logger.error(f"[Worker] ❌ Không kết nối được Redis: {e}")
        sys.exit(1)

    queues = [Queue(QUEUE_NAME, connection=conn, default_timeout=JOB_TIMEOUT)]
    worker = Worker(queues, connection=conn)

    logger.info(f"[Worker] 🚀 Bắt đầu lắng nghe queue '{QUEUE_NAME}'...")
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
