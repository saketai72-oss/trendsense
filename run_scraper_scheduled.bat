@echo off
:: TrendSense — Scheduled Scraper (chạy trên máy local)
:: Tạo task trong Task Scheduler để chạy tự động mỗi 4 giờ
::
:: Setup:
:: 1. Mở Task Scheduler (Win+R → taskschd.msc)
:: 2. Create Basic Task → Name: "TrendSense Scraper"
:: 3. Trigger: Daily → Repeat every 4 hours
:: 4. Action: Start a program → Browse đến file này

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
call venv\Scripts\activate.bat
python -m services.tiktok_scraper.scraper_main >> logs\scraper.log 2>&1
python -m services.ai_engine.ai_core_main >> logs\ai_worker.log 2>&1
