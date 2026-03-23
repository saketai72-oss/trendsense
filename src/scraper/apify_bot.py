import sys
import os
import pandas as pd
import requests
from apify_client import ApifyClient
from dotenv import load_dotenv

# Khai báo cho Python biết thư mục gốc ở đâu để import file settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# ==========================================
# PHẦN 1: KHỞI TẠO BOT VỚI CẤU HÌNH TỪ SETTINGS
# ==========================================
if not settings.APIFY_TOKEN:
    print("[!] LỖI: Không tìm thấy API Token trong file .env")
    exit()

client = ApifyClient(settings.APIFY_TOKEN)

print(f"\n[*] Đang cào CHÍNH XÁC {settings.MAX_VIDEOS_TO_SCRAPE} video...")

run_input = {
    "hashtags": settings.TARGET_KEYWORDS, 
    "maxItems": settings.MAX_VIDEOS_TO_SCRAPE, 
    "maxComments": 15, 
    "commentsPerPost": 15,
    "shouldDownloadVideos": False,
    "shouldDownloadCovers": False
}

# ==========================================
# PHẦN 2: CÀO DỮ LIỆU TỐI ƯU CHI PHÍ (1 BƯỚC DUY NHẤT)
# ==========================================
print(f"\n[*] Đang cào CHÍNH XÁC {settings.MAX_VIDEOS_TO_SCRAPE} video để tiết kiệm Credit...")

run_input = {
    "hashtags": ["xuhuong", "viral"], 
    "maxItems": settings.MAX_VIDEOS_TO_SCRAPE, 
    "maxComments": 15, 
    "commentsPerPost": 15,
    "shouldDownloadVideos": False,
    "shouldDownloadCovers": False
}

# Chỉ gọi Apify ĐÚNG 1 LẦN duy nhất
run = client.actor("clockworks/tiktok-scraper").call(run_input=run_input)
raw_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

print(f"[*] Đã cào xong {len(raw_items)} video gốc. Đang móc nối Comment...")

# ==========================================
# PHẦN 3: TỰ ĐỘNG TẢI COMMENT MIỄN PHÍ TỪ LINK PHỤ
# ==========================================
for item in raw_items:
    dataset_url = item.get("commentsDatasetUrl")
    item["comments"] = [] 
    
    if dataset_url:
        try:
            res = requests.get(dataset_url)
            if res.status_code == 200:
                item["comments"] = res.json()
        except Exception as e:
            pass

# ==========================================
# PHẦN 4: LƯU KHO DATA LAKE RAW BẰNG ĐƯỜNG DẪN TỪ SETTINGS
# ==========================================
df_new = pd.json_normalize(raw_items)

if 'webVideoUrl' in df_new.columns:
    df_new.rename(columns={'webVideoUrl': 'Link'}, inplace=True)

# Lấy đường dẫn file từ settings
if os.path.exists(settings.RAW_FILE):
    df_old = pd.read_csv(settings.RAW_FILE, low_memory=False)
    df_final = pd.concat([df_old, df_new], ignore_index=True)
    if 'Link' in df_final.columns:
        df_final.drop_duplicates(subset=['Link'], keep='last', inplace=True) 
else:
    df_final = df_new

df_final.to_csv(settings.RAW_FILE, index=False, encoding='utf-8-sig')

print(f"\n[*] Đã lưu vào kho dữ liệu thô thành công!")