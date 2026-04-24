import sys
import os

# Thêm đường dẫn gốc để import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.session import get_connection

def migrate():
    print("🚀 Đang kiểm tra và cập nhật cấu trúc database...")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Kiểm tra xem cột is_rescraped đã tồn tại chưa
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='videos' AND column_name='is_rescraped';
            """)
            if not cursor.fetchone():
                print("  [+] Đang thêm cột is_rescraped vào bảng videos...")
                cursor.execute("ALTER TABLE videos ADD COLUMN is_rescraped BOOLEAN DEFAULT FALSE;")
                cursor.execute("CREATE INDEX idx_is_rescraped ON videos(is_rescraped);")
                print("  [✓] Đã thêm cột thành công.")
            else:
                print("  [i] Cột is_rescraped đã tồn tại.")
            
            conn.commit()
    except Exception as e:
        print(f"[ERROR] Lỗi migration: {e}")
        conn.rollback()
    finally:
        conn.close()
    print("✨ Xong!")

if __name__ == "__main__":
    migrate()
