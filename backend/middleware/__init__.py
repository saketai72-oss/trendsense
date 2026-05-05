"""
Backend Middleware Stack
========================
Tất cả custom middleware tập trung tại đây để main.py chỉ cần import.
"""
from backend.middleware.request_id import RequestIDMiddleware
from backend.middleware.logging import RequestLoggingMiddleware
from backend.middleware.security import SecurityHeadersMiddleware
from backend.middleware.error_handler import register_error_handlers

__all__ = [
    "RequestIDMiddleware",
    "RequestLoggingMiddleware",
    "SecurityHeadersMiddleware",
    "register_error_handlers",
]
