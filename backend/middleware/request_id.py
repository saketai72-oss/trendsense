"""
Request ID Middleware
=====================
Tạo UUID4 cho mỗi request, gắn vào request.state và response header X-Request-ID.
Cho phép trace toàn bộ lifecycle của một request qua log.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
