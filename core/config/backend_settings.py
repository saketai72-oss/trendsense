import os
from core.config.base import *

# Frontend URL for CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Standard Video Categories
STANDARD_CATEGORIES = [
    "Giải trí", "Giáo dục", "Công nghệ", "Ẩm thực", "Thể thao",
    "Làm đẹp & Thời trang", "Đời sống", "Tài chính", "Tin tức", "Khác"
]
