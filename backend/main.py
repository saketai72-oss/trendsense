"""
TrendSense Backend — FastAPI Application
=========================================
Cung cấp REST API cho React Frontend.
Chạy: python -m uvicorn backend.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from core.config.backend_settings import FRONTEND_URL

app = FastAPI(
    title="TrendSense API",
    description="AI-Powered TikTok Viral Prediction System",
    version="2.0.0",
)

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
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
    }
