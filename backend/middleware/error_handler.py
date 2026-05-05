"""
Global Error Handler
=====================
Bắt mọi exception chưa được xử lý, trả về JSON 500 thay vì stack trace.
Production: ẩn chi tiết lỗi, chỉ log nội bộ.
Development: trả traceback để debug nhanh.
"""
import logging

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("trendsense.error")


def register_error_handlers(app: FastAPI) -> None:
    """Đăng ký exception handler vào FastAPI app (không bắt HTTPException)."""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Để FastAPI/Starlette tự xử lý HTTPException
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            raise exc

        request_id = getattr(request.state, "request_id", "-")
        logger.error(
            "Unhandled error [%s] %s %s: %s",
            request_id,
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )

        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
