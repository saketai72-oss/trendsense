# TrendSense — Hướng dẫn chạy scraper trên máy local

## Tại sao không chạy trên GitHub Actions?

TikTok chặn **tất cả IP datacenter** (GitHub Actions, Cloudflare, Vercel...).
Chỉ IP residential (mạng nhà) mới truy cập được TikTok.

## Setup Task Scheduler (Windows)

### Bước 1: Tạo thư mục logs
```cmd
mkdir logs
```

### Bước 2: Mở Task Scheduler
- Win+R → `taskschd.msc` → Enter

### Bước 3: Tạo task mới
1. **Create Basic Task**
2. Name: `TrendSense Scraper`
3. Trigger: **Daily** → Advanced → Repeat task every: **4 hours** → Duration: **Indefinitely**
4. Action: **Start a program**
   - Program: `c:\Users\saket\Codes\TrendSense\run_scraper_scheduled.bat`
   - Start in: `c:\Users\saket\Codes\TrendSense`
5. Finish

### Bước 4: Test chạy thử
```cmd
c:\Users\saket\Codes\TrendSense\run_scraper_scheduled.bat
```

## Logs

Logs được lưu tại `logs/scraper.log`. Xem log:
```cmd
type logs\scraper.log
```

## Lưu ý

- Máy phải **bật** khi task chạy
- Scraper dùng ~500MB RAM, không ảnh hưởng đến công việc khác
- Nếu muốn tắt máy → dùng **Hibernate** thay vì Shutdown (task vẫn chạy khi wake up)
