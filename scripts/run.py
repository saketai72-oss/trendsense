import subprocess
import sys
import os

def run_script(script_path, is_streamlit=False):
    """Hàm chạy các file Python và bắt lỗi nếu có"""
    print(f"[*] DANG CHAY: {script_path}")
    print(f"{'='*60}\n")

    try:
        if is_streamlit:
            subprocess.run([sys.executable, "-m", "streamlit", "run", script_path], check=True)
        else:
            subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] ❌ HỆ THỐNG PHÁT HIỆN LỖI KHI CHẠY: {script_path}")
        print("[!] 🛑 Dừng toàn bộ tiến trình để bảo vệ dữ liệu.")
        sys.exit(1)

if __name__ == "__main__":
    print("--- BAT DAU KHOI DONG HE THONG TU DONG TRENDSENSE ---")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    scraper_main = os.path.join(BASE_DIR, "src", "scraper", "scraper_main.py")
    ai_core_main = os.path.join(BASE_DIR, "src", "ai_core", "ai_core_main.py")
    app_script = os.path.join(BASE_DIR, "src", "dashboard", "app.py")

    # ---------------------------------------------------------
    # BƯỚC 1: KÍCH HOẠT BOT CÀO DỮ LIỆU → GHI VÀO SQLITE
    # ---------------------------------------------------------
    run_script(scraper_main)

    # ---------------------------------------------------------
    # BƯỚC 2: AI CORE — NLP (chỉ video mới) + PREDICT (model sẵn)
    # ---------------------------------------------------------
    run_script(ai_core_main)

    # ---------------------------------------------------------
    # BƯỚC 3: MỞ TRANG TỔNG QUAN (DASHBOARD)
    # ---------------------------------------------------------
    print("\n[V] DU LIEU DA CAP NHAT HOAN TAT! DANG MO DASHBOARD...\n")
    run_script(app_script, is_streamlit=True)