import sys
import os

# Thêm đường dẫn gốc của project để có thể import module core
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.session import get_connection

def reset_khac_videos():
    """
    Tìm các video có danh mục là '🌍 Khác' hoặc chưa được phân loại (mảng rỗng)
    và chuyển trạng thái về 'pending' để AI phân tích lại.
    Loại trừ các video có trạng thái lỗi hoặc danh mục lỗi.
    """
    print(" [~] Đang tìm kiếm các video có danh mục 'Khác' để reset...")
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Tìm các video có category chứa '🌍 Khác' hoặc là mảng rỗng [] 
            # mà không phải đang ở trạng thái pending/downloading/analyzing
            # Loại trừ lỗi (ai_status = 'error' hoặc category chứa 'Lỗi')
            
            query = """
                UPDATE videos 
                SET ai_status = 'pending',
                    category = '{}',
                    video_description = NULL,
                    top_keywords = NULL
                WHERE (
                    '🌍 Khác' = ANY(category) 
                    OR category = '{}'
                )
                AND ai_status NOT IN ('error', 'pending', 'downloading', 'analyzing', 'summarizing')
                AND NOT ('Lỗi' = ANY(category));
            """
            
            cursor.execute(query)
            count = cursor.rowcount
            
            conn.commit()
            print(f" [✓] Đã reset thành công {count} video về trạng thái 'pending'.")
            if count > 0:
                print(" [!] Các video này sẽ được AI Worker tự động xử lý lại trong lượt tới.")
            else:
                print(" [i] Không tìm thấy video nào cần reset.")
                
    except Exception as e:
        conn.rollback()
        print(f" [!] Lỗi khi thực thi script: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    reset_khac_videos()
