import subprocess
import sys
import os

def run_script(script_path, is_streamlit=False):
    """Hàm chạy các file Python và bắt lỗi nếu có"""
    print(f"\n{'='*60}")
    print(f"🚀 ĐANG CHẠY: {script_path}")
    print(f"{'='*60}\n")
    
    try:
        if is_streamlit:
            # Lệnh dành riêng cho Streamlit
            subprocess.run([sys.executable, "-m", "streamlit", "run", script_path], check=True)
        else:
            # Lệnh chạy file Python bình thường
            subprocess.run([sys.executable, script_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[!] ❌ HỆ THỐNG PHÁT HIỆN LỖI KHI CHẠY: {script_path}")
        print("[!] 🛑 Dừng toàn bộ tiến trình để bảo vệ dữ liệu.")
        sys.exit(1)

if __name__ == "__main__":
    print("🌟 BẮT ĐẦU KHỞI ĐỘNG HỆ THỐNG TỰ ĐỘNG TRENDSENSE 🌟")
    
    # Định vị đường dẫn các module
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    scraper_script = os.path.join(BASE_DIR, "src", "scraper", "apify_bot.py")
    nlp_script = os.path.join(BASE_DIR, "src", "ai_core", "nlp_model.py")
    predictive_script = os.path.join(BASE_DIR, "src", "ai_core", "predictive_model.py")
    app_script = os.path.join(BASE_DIR, "src", "dashboard", "app.py")
    
    # ---------------------------------------------------------
    # BƯỚC 1: KÍCH HOẠT BOT CÀO DỮ LIỆU
    # ---------------------------------------------------------
    run_script(scraper_script)
    
    # ---------------------------------------------------------
    # BƯỚC 2: KÍCH HOẠT AI ĐỌC HIỂU & CHẤM ĐIỂM
    # ---------------------------------------------------------
    run_script(nlp_script)
    
    # ---------------------------------------------------------
    # BƯỚC 3: KÍCH HOẠT MÔ HÌNH DỰ BÁO
    # ---------------------------------------------------------
    run_script(predictive_script)
    
    # ---------------------------------------------------------
    # BƯỚC 4: MỞ TRANG TỔNG QUAN (DASHBOARD)
    # ---------------------------------------------------------
    print("\n🎉 DỮ LIỆU ĐÃ CẬP NHẬT HOÀN TẤT! ĐANG MỞ DASHBOARD...\n")
    run_script(app_script, is_streamlit=True)