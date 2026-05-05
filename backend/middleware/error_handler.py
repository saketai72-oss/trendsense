"""
Global Error Handler
=====================
Bắt mọi exception chưa được xử lý, trả về JSON 500 thay vì stack trace.
Production: ẩn chi tiết lỗi, chỉ log nội bộ.
Development: trả traceback để debug nhanh.
"""
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("trendsense.error")


def register_error_handlers(app: FastAPI) -> None:
    """Đăng ký exception handlers vào FastAPI app."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "-")
        logger.error(
            "Unhandled error [%s] %s %s: %s",
            request_id,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )

        # Production: không leak internals
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
