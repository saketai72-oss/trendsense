"""
TrendSense Backend — FastAPI Application
=========================================
Cung cấp REST API cho React Frontend.
Chạy: python -m uvicorn backend.main:app --reload --port 8000

Render Free Tier: RQ Worker chạy in-process via threading.Thread(daemon=True)
trong lifespan event — job vẫn an toàn trên Upstash Redis khi container restart.
"""
import logging
import threading
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

# ── RQ Worker In-Process (Render Free Tier Workaround) ────────────────────────
#
# Root cause của lỗi "signal only works in main thread":
#   BaseWorker.work() luôn gọi self.setup_signal_handlers() trước khi listen.
#   setup_signal_handlers() dùng signal.signal() — chỉ hoạt động trên main thread.
#   SimpleWorker trong RQ 2.8.0 KHÔNG override hàm này → vẫn lỗi trong thread.
#
# Fix: Subclass SimpleWorker, override setup_signal_handlers() thành no-op hoàn toàn.
# Render kill container bằng SIGTERM gửi tới main process (uvicorn) → daemon thread
# tự die theo — không cần graceful shutdown handler.

def _run_rq_worker() -> None:
    """
    Chạy ThreadSafeWorker (SimpleWorker subclass) trong daemon thread.
    ThreadSafeWorker.setup_signal_handlers() là no-op → không raise ValueError.
    Job timeout (900s) và retry logic vẫn hoạt động bình thường.
    ssl_cert_reqs=None: bypass TLS cert check cho Upstash rediss:// URL.
    """
    import os
    try:
        from redis import Redis
        from rq import SimpleWorker, Queue

        # ── ThreadSafeWorker: override signal setup thành no-op ──────────────
        class ThreadSafeWorker(SimpleWorker):
            def setup_signal_handlers(self) -> None:
                """
                No-op: signal.signal() chỉ hoạt động trên main thread.
                Daemon thread tự die khi uvicorn process thoát (SIGTERM → main).
                Không cần graceful shutdown handler trong thread context.
                """
                pass
        # ─────────────────────────────────────────────────────────────────────

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        logger.info("[Worker] Đang kết nối Redis: %s", redis_url[:40] + "...")

        conn = Redis.from_url(redis_url, ssl_cert_reqs=None)
        conn.ping()
        logger.info("[Worker] ✅ Redis connected")

        queue = Queue("gemini_jobs", connection=conn, default_timeout=900)
        worker = ThreadSafeWorker([queue], connection=conn)

        logger.info("[Worker] 🚀 Lắng nghe queue 'gemini_jobs' (ThreadSafeWorker)...")
        worker.work(burst=False)

    except Exception as exc:
        logger.error("[Worker] ❌ Worker thread gặp lỗi, dừng lại: %s", exc)


# ── Lifespan — Startup / Shutdown ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager thay thế @app.on_event (deprecated trong FastAPI ≥ 0.93).

    Startup:
        - Spawn RQ Worker thread (daemon) → xử lý gemini_jobs từ Upstash Redis.
    Shutdown:
        - Daemon thread tự die khi uvicorn process thoát. Không cần cleanup thủ công.
    """
    logger.info("[Lifespan] 🚀 TrendSense backend đang khởi động...")

    worker_thread = threading.Thread(
        target=_run_rq_worker,
        daemon=True,          # Die cùng main process
        name="rq-gemini-worker",
    )
    worker_thread.start()
    logger.info("[Lifespan] 🧵 RQ Worker thread started (id=%s)", worker_thread.ident)

    yield  # ← App đang chạy, nhận request ở đây

    logger.info("[Lifespan] 🛑 TrendSense backend đang shutdown...")


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
