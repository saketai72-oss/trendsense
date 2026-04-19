import psycopg2
from core.config.base import DATABASE_URL

def get_connection():
    """Tạo kết nối tới Supabase PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn
