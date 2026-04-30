"""
TrendSense Backend — FastAPI Application
=========================================
Cung cấp REST API cho React Frontend.
Chạy: python -m uvicorn backend.main:app --reload --port 8000
"""
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

app = FastAPI(
    title="TrendSense API",
    description="AI-Powered TikTok Viral Prediction System",
    version="3.0.0",
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
