import os
import sqlite3
import sys

# Khai báo đường dẫn gốc để import được config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

DB_FILE = settings.DB_FILE

def init_db():
    """Khởi tạo database và tạo bảng nếu chưa có"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Tạo bảng với video_id là Khóa chính (Primary Key) giúp tốc độ tìm kiếm cực nhanh
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            video_id TEXT PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def is_scraped(video_id):
    """Kiểm tra xem video đã bị cào chưa"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM history WHERE video_id = ?', (video_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_as_scraped(video_id):
    """Lưu ID video vào database sau khi cào xong"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO history (video_id) VALUES (?)', (video_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        # Bỏ qua nếu ID đã tồn tại (phòng hờ)
        pass
    conn.close()

def extract_video_id(url):
    """Cắt lấy đúng cái dãy số ID từ link TikTok"""
    try:
        # Tách phần sau chữ /video/ và bỏ đi các tham số thừa sau dấu ?
        return url.split('/video/')[1].split('?')[0]
    except:
        return None