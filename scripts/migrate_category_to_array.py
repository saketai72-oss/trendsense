import sys
import os

# Add root project path so we can import core module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.db.session import get_connection

def migrate():
    print("Starting database migration: category TEXT -> TEXT[]")
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if it already migrated
            cursor.execute("SELECT data_type FROM information_schema.columns WHERE table_name = 'videos' AND column_name = 'category'")
            res = cursor.fetchone()
            if res and res[0] == 'ARRAY':
                print("Column 'category' is already of type ARRAY. Migration skipped.")
                return

            print("1. Adding temporary categories_array column...")
            cursor.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS categories_array TEXT[];")
            
            print("2. Migrating data...")
            cursor.execute("""
                UPDATE videos 
                SET categories_array = string_to_array(category, ' | ') 
                WHERE category IS NOT NULL AND category != '';
            """)
            
            print("3. Fixing 'error' statuses for fallback videos...")
            cursor.execute("""
                UPDATE videos 
                SET ai_status = 'error' 
                WHERE category = '🌍 Khác' 
                   OR video_description ILIKE '%Lỗi khi gọi%';
            """)
            
            cursor.execute("""
                UPDATE videos 
                SET categories_array = array_remove(categories_array, '🌍 Khác')
                WHERE '🌍 Khác' = ANY(categories_array);
            """)

            print("4. Replacing old column...")
            cursor.execute("ALTER TABLE videos DROP COLUMN category;")
            cursor.execute("ALTER TABLE videos RENAME COLUMN categories_array TO category;")
            
            print("5. Creating GIN Index...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category_gin ON videos USING GIN(category);")
            
            conn.commit()
            print("Migration completed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
