"""
TrendSense Backend — FastAPI Application
=========================================
Cung cấp REST API cho React Frontend.
Chạy: python -m uvicorn backend.main:app --reload --port 8000

Render Free Tier:
  RQ Worker chạy như subprocess độc lập (không phải thread) để tránh lỗi
  "signal only works in main thread" — signal.signal() cần main thread của
  từng process, không hoạt động trong daemon thread của uvicorn.
"""
import logging
import subprocess
import sys
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.api.routes import router
from core.config.backend_settings import FRONTEND_URL, REDIS_URL

from backend.api.rate_limiter import limiter

logger = logging.getLogger("trendsense.main")


# ── RQ Worker Subprocess (Render Free Tier Workaround) ────────────────────────
#
# Tại sao dùng subprocess thay threading.Thread:
#
#   signal.signal() CHỈ hoạt động trên main thread của main interpreter.
#   Mọi cách dùng thread (Worker, SimpleWorker, subclass) đều fail vì RQ
#   gọi signal.signal() ở NHIỀU chỗ: setup_signal_handlers(), vòng lặp dequeue
#   (SIGALRM cho job timeout), và scheduler.
#
#   Subprocess có main thread RIÊNG → signal hoạt động bình thường.
#   Render kill container bằng SIGTERM → PID 1 → tất cả child processes đều die.
#   backend/worker.py đã tự thêm project root vào sys.path → chạy được độc lập.

def _start_rq_worker_process() -> subprocess.Popen:
    """
    Khởi động backend/worker.py như subprocess độc lập.
    Kế thừa toàn bộ env vars từ Render (DATABASE_URL, REDIS_URL, v.v.).
    Trả về Popen object để lifespan có thể terminate khi shutdown.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "backend.worker"],
        env=os.environ.copy(),   # Kế thừa env vars từ Render
        # stdout/stderr kế thừa từ parent → log xuất ra Render log stream
    )
    logger.info("[Worker] 🚀 RQ Worker subprocess started (PID=%s)", proc.pid)
    return proc


# ── Lifespan — Startup / Shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: Spawn RQ Worker subprocess → xử lý gemini_jobs từ Upstash Redis.
    Shutdown: Terminate subprocess (Render kill container → tất cả processes die).
    """
    logger.info("[Lifespan] 🚀 TrendSense backend đang khởi động...")

    worker_proc = _start_rq_worker_process()

    yield  # ← App đang chạy, nhận request ở đây

    logger.info(
        "[Lifespan] 🛑 Shutdown — dừng RQ Worker (PID=%s)...", worker_proc.pid
    )
    worker_proc.terminate()


# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="TrendSense API",
    description="AI-Powered TikTok Viral Prediction System",
    version="3.0.0",
    lifespan=lifespan,
)

# Gắn limiter vào app state để routes có thể dùng
app.state.limiter = limiter

# Middleware: xử lý RateLimitExceeded → 429 JSON
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — cho phép Frontend React kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "name": "TrendSense API",
        "version": "3.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """
    Lightweight keep-alive endpoint cho UptimeRobot.
    Ping mỗi 14 phút để ngăn Render Free Tier sleep.
    KHÔNG query DB — chỉ trả JSON tức thì để giảm latency.
    """
    return {"status": "ok"}
