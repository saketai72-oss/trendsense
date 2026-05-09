import time
import psycopg2
from core.config.base import DATABASE_URL

def get_connection(max_retries=3, delay=2):
    """Tạo kết nối tới Supabase PostgreSQL với cơ chế retry."""
    last_err = None
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            conn.autocommit = False
            return conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            last_err = e
            print(f"  [⟳] DB Connection failed (attempt {attempt+1}/{max_retries}): {str(e)[:100]}")
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
    
    print(f"[!] ❌ Không thể kết nối DB sau {max_retries} lần thử.")
    if last_err:
        raise last_err
    raise psycopg2.OperationalError("Database connection failed after maximum retries.")
