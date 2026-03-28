import pandas as pd
import os
import sys
from datasets import load_dataset

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

def main():
    print("[*] Đang tải dataset SIÊU NHẸ 'datahiveai/Tiktok-Videos'...")
    # Bộ này thuần Text/CSV, không chứa bất kỳ video nào. Tải 2 giây là xong!
    dataset = load_dataset(
        "datahiveai/Tiktok-Videos", 
        split="train", 
        token=settings.HF_TOKEN
    )
    
    df = dataset.to_pandas()
    print(f"\n[+] Đã tải xong {len(df)} dòng dữ liệu!")

    # Cập nhật từ điển đổi tên cột cho khớp với bộ mới này
    rename_map = {
        'url': 'Link', 
        'play_count': 'Views',
        'digg_count': 'Likes',
        'comment_count': 'Comments',
        'share_count': 'Shares',
        'collect_count': 'Saves'
    }
    df = df.rename(columns=rename_map)

    # Bộ này chỉ chuyên về số liệu tương tác, không có Caption hay Create_Time.
    # Chúng ta tự động bơm giá trị rỗng vào để Form của tool không bị gãy.
    if 'Caption' not in df.columns: df['Caption'] = ""
    if 'Create_Time' not in df.columns: df['Create_Time'] = 0

    cols_to_keep = ['Link', 'Create_Time', 'Caption', 'Views', 'Likes', 'Comments', 'Shares', 'Saves']
    final_cols = [col for col in cols_to_keep if col in df.columns]
    df_clean = df[final_cols]
    
    df_clean = df_clean.fillna(0)
    
    # Ghi thẳng vào nhà kho, sẵn sàng cho AI ăn
    df_clean.to_csv(settings.RAW_FILE, index=False, encoding='utf-8-sig')

    print(f"\n[+] XONG! Dữ liệu đã an vị tại {settings.RAW_FILE}")
    print("[*] 👉 BƯỚC TIẾP THEO: Cậu mở file predictive_model.py lên chạy luôn, AI sẽ có đủ data để train!")

if __name__ == "__main__":
    main()