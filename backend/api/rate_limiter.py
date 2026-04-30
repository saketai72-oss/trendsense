import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from core.config.backend_settings import REDIS_URL

try:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=REDIS_URL,
    )
except Exception:
    logging.getLogger(__name__).warning(
        "[RateLimit] Không kết nối được Redis, dùng memory storage (không production-safe)."
    )
    limiter = Limiter(key_func=get_remote_address)
