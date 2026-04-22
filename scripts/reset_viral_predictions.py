import os
import sys
from datetime import datetime, timedelta

# Add project root to sys.path to allow importing from 'core'
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import DB connection logic
try:
    from core.db.session import get_connection
except ImportError:
    print("Error: Could not import core.db.session. Ensure the script is run from the project root or 'scripts' directory.")
    sys.exit(1)

def reset_old_viral_videos():
    """
    Duyệt qua các video đã được dự đoán viral (viral_probability > 0).
    Nếu video đã quá 2 tuần (14 ngày) tính từ ngày scrape, reset dự đoán về 0.
    """
    print(f"--- Starting Weekly Viral Status Cleanup: {datetime.now()} ---")
    
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Calculate 2 weeks in seconds
            two_weeks_seconds = 14 * 24 * 60 * 60
            current_timestamp = int(datetime.now().timestamp())
            cutoff_timestamp = current_timestamp - two_weeks_seconds
            
            print(f"Targeting videos created before timestamp: {cutoff_timestamp} (older than 2 weeks)")

            # Query to reset viral metrics for old videos
            # Consistent with prediction_engine.py logic (create_time based)
            query = """
                UPDATE videos 
                SET viral_probability = 0
                WHERE create_time > 0 
                  AND create_time < %s 
                  AND viral_probability > 0
            """
            
            cursor.execute(query, (cutoff_timestamp,))
            updated_count = cursor.rowcount
            
            conn.commit()
            print(f"Successfully reset viral status for {updated_count} videos.")
            
    except Exception as e:
        print(f"CRITICAL ERROR during cleanup: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    
    print("--- Cleanup Process Finished ---")

if __name__ == "__main__":
    reset_old_viral_videos()
