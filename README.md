# 🎯 TrendSense: AI-Powered TikTok Viral Prediction Radar

TrendSense là hệ thống phân tích xu hướng và dự báo khả năng bùng nổ (viral probability) cho video TikTok dựa trên phân tích đa phương thức (Multimodal AI) và máy học (Machine Learning).

## 🚀 Kiến trúc Hybrid (Mới)

Dự án đã được chuyển đổi sang kiến trúc Hybrid Pipeline để tối ưu hóa tài nguyên:

1.  **Vệ tinh - Data Scraping (GitHub Actions):**
    *   Chạy định kỳ mỗi 4 giờ trên đám mây.
    *   Sử dụng Selenium + Undetected Chromedriver để cào dữ liệu thô.
    *   **Lọc ngôn ngữ:** Sử dụng `langdetect` để chỉ giữ lại video Tiếng Việt.
    *   **Lưu trữ:** Đẩy dữ liệu trực tiếp lên **Supabase (PostgreSQL)** với trạng thái `ai_status = 'pending'`.

2.  **Trạm Mẹ - AI Worker (Local PC / Legion 5):**
    *   Kéo các bản ghi `pending` từ Supabase về xử lý nội bộ.
    *   **Multimodal Engine:**
        *   **Whisper:** Chuyển đổi âm thanh sang văn bản (Transcript).
        *   **EasyOCR:** Đọc chữ xuất hiện trên màn hình.
        *   **BLIP:** Mô tả bối cảnh hình ảnh (Image Captioning).
        *   **Ollama:** Tổng hợp dữ liệu từ 3 nguồn trên thành mô tả nội dung bằng Tiếng Việt.
    *   **Sentiment Analysis:** Phân tích cảm xúc từ top comment.
    *   **RandomForest Model:** Dự báo xác suất viral dựa trên các chỉ số tương tác và cảm xúc.

3.  **Visualization - Streamlit Dashboard:**
    *   Hiển thị báo cáo thời gian thực từ Cloud DB.
    *   Phân tích đa chiều: Tốc độ lan truyền (Viral Velocity), bản đồ tương tác, radar chart.

## 🛠️ Cấu trúc thư mục

```
TrendSense/
├── .github/workflows/    # Cấu hình tự động cào data (CI/CD)
├── config/               # Cấu hình hệ thống (settings.py)
├── data/                 # Lưu trữ model ML (.joblib) và dữ liệu tạm
├── src/
│   ├── scraper/          # Module cào dữ liệu, xử lý DB (Postgres)
│   ├── ai_core/          # Engine AI, NLP, Multimodal, Prediction
│   └── dashboard/        # Giao diện Streamlit
└── requirements.txt      # Danh sách thư viện cần thiết
```

## ⚙️ Cài đặt & Sử dụng

### 1. Cấu hình môi trường
Tạo file `.env` tại thư mục gốc:
```env
DATABASE_URL=postgresql://postgres:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?prepare_threshold=0
ST_DATABASE_URL=postgresql://... # Link cho Streamlit nếu cần
OLLAMA_URL=http://localhost:11434/api/generate
```

### 2. Chạy Dashboard
```bash
streamlit run src/dashboard/app.py
```

### 3. Chạy AI Worker (Xử lý các video 'pending')
```bash
python src/ai_core/ai_core_main.py
```

## 📊 Công thức Viral Velocity
Hệ thống sử dụng công thức độc quyền để đánh giá tốc độ lan truyền:
`Velocity = (Views/Giờ × Engagement Rate) / log₁₀(Tuổi Video + 10)`

---
*Phát triển bởi TrendSense Team — Hệ thống dự báo xu hướng tương lai.*
