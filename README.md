# TrendSense

> Nền tảng phân tích và dự đoán xu hướng video ngắn (TikTok) bằng Trí tuệ nhân tạo (AI).

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Node](https://img.shields.io/badge/node-%3E%3D20-green)
![Status](https://img.shields.io/badge/status-active-success)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Environment Variables](#environment-variables)
- [Installation](#installation)
- [Development](#development)
- [Production Deployment](#production-deployment)
- [Database](#database)
- [API Documentation](#api-documentation)
- [Authentication](#authentication)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Logging & Monitoring](#logging--monitoring)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

**TrendSense** là một nền tảng phân tích dữ liệu mạng xã hội tập trung vào các video ngắn (hiện tại hỗ trợ TikTok). Hệ thống giúp các nhà sáng tạo nội dung (Content Creators), Marketers và doanh nghiệp:

- Tự động thu thập siêu dữ liệu (metadata) video mà không cần qua API chính thức.
- Phân tích cảm xúc người xem (Sentiment Analysis) và trích xuất từ khóa bằng các Mô hình Ngôn ngữ Lớn (LLM).
- Tính toán và dự đoán khả năng lan truyền (Viral Velocity) của video.
- Cung cấp Dashboard trực quan để theo dõi hiệu suất và tối ưu hóa chiến lược nội dung.

---

## Features

### Core Features

- **Tài khoản & Phân quyền:** Đăng nhập, đăng ký và quản lý người dùng với JWT.
- **Data Scraping tự động:** Cào dữ liệu video (views, likes, comments, metadata) thông qua link chia sẻ.
- **Dashboard Thống kê:** Biểu đồ Radar, Timeline, thống kê hiệu suất video trực quan.
- **Thanh toán tự động (Pro):** Nâng cấp tài khoản Pro qua mã QR ngân hàng (VietQR) tích hợp Webhook SePay, xử lý tự động trong 3 giây.
- **Quản lý Hàng đợi:** Sử dụng Redis Queue (RQ) để xử lý lượng lớn request mà không gây nghẽn server.

### AI Features

- **Tóm tắt nội dung:** AI tự động đọc hiểu phụ đề (transcript) và nội dung video.
- **Đánh giá Cảm xúc (Sentiment):** Phân loại bình luận thành Tích cực, Tiêu cực, Trung lập.
- **Trích xuất Từ khóa:** Tự động bắt các hashtag và từ khóa đang thịnh hành.
- **Chấm điểm Viral:** Công thức kết hợp AI và hệ số tương tác để dự đoán mức độ thành công của video.
- **Cơ chế Fallback thông minh:** Tự động chuyển đổi giữa Google Gemini và Groq/LLaMA khi gặp lỗi Rate Limit.

---

## Tech Stack

### Frontend

- **Framework:** Next.js 14 (App Router)
- **UI Library:** React, TailwindCSS
- **State Management:** React Context / Hooks
- **Data Fetching:** Fetch API, Axios

### Backend

- **Framework:** FastAPI (Python 3.11+)
- **Task Queue:** Redis & RQ (Redis Queue)
- **Scraping Engine:** yt-dlp

### Database

- **Cơ sở dữ liệu chính:** PostgreSQL
- **BaaS:** Supabase (Quản lý Database & Storage)

### AI / Tooling

- **Large Language Models:** Google Gemini 1.5 Flash, Groq (Llama 3)
- **Embedding:** Ollama (tùy chọn local)

### DevOps

- **Hosting:** Render (Backend), Vercel (Frontend)
- **CI/CD:** GitHub Actions (tùy chọn)

---

## Architecture

```text
       [ Người dùng / Content Creator ]
                 |
                 v
      Frontend (Next.js + Tailwind)
                 | (REST API / JWT)
                 v
        Backend API (FastAPI) <────────> Database (PostgreSQL / Supabase)
                 |
        (Enqueue Task via Redis)
                 |
                 v
        Worker Node (RQ Worker)
                 |
    +────────────┴────────────+
    |                         |
Scraping Engine           AI Engine
  (yt-dlp)          (Google Gemini / Groq)
```

### Architecture Notes

- Frontend giao tiếp hoàn toàn qua RESTful API.
- Kiến trúc xử lý bất đồng bộ: Các tác vụ nặng (Cào dữ liệu, Gọi AI) được đẩy vào Redis Queue thay vì chạy trên luồng chính của FastAPI.
- Mô hình lưu trữ: Sử dụng Repository pattern để tương tác với Supabase PostgreSQL.

---

## Project Structure

```bash
trendsense/
│
├── backend/                # FastAPI application
│   ├── api/                # API Routes & Controllers
│   ├── auth/               # JWT & Security
│   ├── worker.py           # RQ Worker process
│   └── main.py             # FastAPI App entry
│
├── core/                   # Cấu hình lõi & Database
│   ├── config/             # Environment settings
│   └── db/                 # Database Models & Session
│
├── services/               # Dịch vụ nghiệp vụ (Business logic)
│   ├── ai_engine/          # Gemini/Groq LLM Integration
│   └── tiktok_scraper/     # yt-dlp Scraping logic
│
├── frontend/               # Next.js Application
│   ├── app/                # Pages & Layouts (App Router)
│   ├── components/         # Reusable UI components
│   └── lib/                # API clients & Utils
│
├── docs/                   # Tài liệu dự án
├── scratch/                # Thư mục chứa script tạm (VD: tạo báo cáo)
├── render.yaml             # Cấu hình deploy Render
└── README.md
```

---

## Environment Variables

Tạo file `.env` (Backend) và `.env.local` (Frontend) dựa trên `.env.example`.

### Backend (`.env`)

```env
# Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres

# Security
JWT_SECRET_KEY=your_super_secret_jwt_key
JWT_ALGORITHM=HS256

# Redis (Queue)
REDIS_URL=redis://default:[PASSWORD]@[HOST]:[PORT]

# AI API Keys
GEMINI_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key

# Webhook Thanh toán
SEPAY_WEBHOOK_TOKEN=your_sepay_token
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8080/api
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/saketai72-oss/trendsense.git
cd trendsense
```

### Install Backend Dependencies

Đảm bảo bạn đang dùng Python 3.11+.

```bash
# Tạo và kích hoạt virtual environment
python -m venv venv
.\venv\Scripts\activate  # (Windows)
# source venv/bin/activate # (Mac/Linux)

# Cài đặt thư viện
pip install -r backend/requirements.txt
pip install -r services/ai_engine/requirements.txt
```

### Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

## Development

### 1. Khởi động Backend (API)

```bash
# Tại thư mục gốc
.\venv\Scripts\activate
uvicorn backend.main:app --reload --port 8080
```

### 2. Khởi động Redis Worker (Xử lý AI)

```bash
# Mở một terminal mới tại thư mục gốc
.\venv\Scripts\activate
python -m rq worker gemini_jobs --url [YOUR_REDIS_URL]
```

### 3. Khởi động Frontend

```bash
cd frontend
npm run dev
# Ứng dụng chạy tại: http://localhost:3000
```

---

## Production Deployment

### Backend (Render)

Hệ thống được tối ưu để deploy lên Render thông qua file `render.yaml`.
Render sẽ tự động cấu hình 1 Web Service (FastAPI) và 1 Background Worker (RQ).

### Frontend (Vercel)

1. Kết nối repo GitHub với Vercel.
2. Build command: `npm run build`
3. Cài đặt biến môi trường `NEXT_PUBLIC_API_URL` trỏ về API Backend của Render.

---

## Database

Hệ thống sử dụng **Supabase (PostgreSQL)**.

### Schema Overview

Các bảng chính trong hệ thống:
- `users`: Quản lý tài khoản, mật khẩu, trạng thái Pro.
- `videos`: Lưu siêu dữ liệu video cào được (views, likes, shares...).
- `video_analyses`: Lưu kết quả trả về từ AI (Sentiment, Keywords, Tóm tắt).
- `subscriptions / payments`: Lịch sử giao dịch VietQR.

---

## API Documentation

Khi Backend đang chạy, truy cập Swagger UI (tự động tạo bởi FastAPI):
👉 **http://localhost:8080/docs**

### Các Endpoint chính

- `POST /api/auth/register` - Đăng ký tài khoản
- `POST /api/auth/login` - Lấy JWT Token
- `POST /api/analyze` - Gửi link TikTok để cào và phân tích
- `GET /api/videos` - Lấy danh sách video đã phân tích
- `POST /api/webhook/sepay` - Nhận callback thanh toán

---

## Authentication

- Sử dụng chuẩn **JSON Web Token (JWT)**.
- Mật khẩu được băm (hash) bằng **Bcrypt** trước khi lưu vào database.
- Các route nhạy cảm được bảo vệ bởi middleware xác thực (`Depends(get_current_user)`).

---

## Testing

*(Tính năng đang phát triển)*

- API Unit Tests sử dụng `pytest`.
- Frontend component tests sử dụng `Jest` và `React Testing Library`.

---

## Logging & Monitoring

- Backend sử dụng module `logging` mặc định của Python với custom format.
- Thông tin về Job (thành công/thất bại, thời gian xử lý) được track chi tiết qua bảng điều khiển RQ và log của Worker.
- API Rate Limiting được áp dụng bằng thư viện `slowapi` để chặn Spam.

---

## Security

- **CORS:** Cấu hình khắt khe chỉ cho phép các domain được chỉ định trong Frontend gọi API.
- **Rate Limiting:** Chặn các request cào dữ liệu liên tục (Ví dụ: 20 request/giờ).
- **Environment Protection:** Các khóa API (Gemini, DB, JWT) tuyệt đối không được push lên GitHub.
- **Webhook Signature:** Xác thực chữ ký mã hóa từ SePay trước khi cộng gói Pro.

---

## Troubleshooting

### Lỗi 429 Too Many Requests (Gemini API)
**Nguyên nhân:** Dùng hết Quota miễn phí của Google Gemini.
**Cách xử lý:** Hệ thống đã có cơ chế tự động Fallback sang Groq API. Đảm bảo bạn đã cấu hình `OPENROUTER_API_KEY` trong file `.env`.

### RQ Worker không chạy hoặc báo lỗi kết nối Redis
**Nguyên nhân:** URL Redis sai hoặc Upstash Redis hết băng thông.
**Cách xử lý:** Kiểm tra lại biến `REDIS_URL` trong `.env`.

### Frontend gọi API báo lỗi CORS
**Nguyên nhân:** Backend chặn domain của Frontend.
**Cách xử lý:** Thêm URL của frontend vào biến danh sách CORS trong `core/config/backend_settings.py`.

---

## Contributing

Chúng tôi hoan nghênh mọi đóng góp!

### Branch Naming

```text
feature/ten-tinh-nang
fix/ten-loi-can-sua
hotfix/loi-nghiem-trong
```

### Commit Convention

```text
feat: Thêm tính năng mới
fix: Sửa lỗi hệ thống
refactor: Tối ưu lại code, không làm đổi chức năng
docs: Cập nhật tài liệu (README)
```

---

## License

Dự án được phân phối dưới giấy phép [MIT License](LICENSE).