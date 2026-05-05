"""
Request Logging Middleware
==========================
Log method, path, status code, và duration (ms) cho mỗi request.
Bỏ qua health-check endpoint để tránh noise.
"""
import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("trendsense.access")

# Không log các endpoint này (keep-alive, health check)
_SKIP_PATHS = {"/health", "/favicon.ico"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        request_id = getattr(request.state, "request_id", "-")
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %d (%.1fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
