import os
import csv

def save_to_csv(all_video_data, filepath):
    if not all_video_data:
        print("[!] Không có dữ liệu mới để lưu.")
        return

    file_exists = os.path.isfile(filepath)
    headers = ['Link', 'Create_Time', 'Caption', 'Views', 'Likes', 'Comments', 'Shares', 'Saves', 
               'Top1_Cmt', 'Top1_Likes', 'Top2_Cmt', 'Top2_Likes', 'Top3_Cmt', 'Top3_Likes', 
               'Top4_Cmt', 'Top4_Likes', 'Top5_Cmt', 'Top5_Likes']

    with open(filepath, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists or os.stat(filepath).st_size == 0:
            writer.writeheader()
        writer.writerows(all_video_data)
    print(f"[+] Đã ghi nối {len(all_video_data)} video vào {filepath}")