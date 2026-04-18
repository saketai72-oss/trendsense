# 🎯 TrendSense: Tóm tắt Dự án (Project Summary)

**TrendSense** là một hệ thống radar dự báo khả năng viral (bùng nổ) của các video trên TikTok. Dự án kết hợp công nghệ Cào dữ liệu (Web Scraping), Trí tuệ Nhân tạo đa phương thức (Multimodal AI) và Mô hình Máy học (Machine Learning) để thu thập, phân tích và đưa ra dự báo.

## 🏗️ Kiến trúc Hệ thống (Hybrid Cloud-Native Architecture)

Dự án hiện tại hoạt động dưới dạng kiến trúc phân tán giữa Cloud và Local (hoặc Modal Serverless), chia làm 3 cụm (module) chính:

### 1. Data Scraping (Thu thập dữ liệu) - `src/scraper/`
- **Công nghệ:** Python, Selenium, `undetected-chromedriver`.
- **Cơ chế:** Hoạt động định kỳ mỗi 4 giờ (điều khiển qua GitHub Actions - `.github/workflows/`). Hệ thống sẽ tự động quét các hashtag đang thịnh hành (hoặc video ngẫu nhiên), thu thập metadata thô (lượt xem, thả tim, bình luận, ngày đăng...). 
- **Chất lượng Data:** Sử dụng `langdetect` để lọc bỏ các nội dung không phải tiếng Việt. 
- **Lưu trữ:** Lưu trữ thẳng lên **Supabase (PostgreSQL Cloud)** với trạng thái chờ xử lý (`ai_status = 'pending'`).

### 2. AI Core (Trung tâm xử lý AI & Dự báo) - `src/ai_core/`
Chịu trách nhiệm kéo dữ liệu chứa trạng thái `pending` về và chạy logic phân tích sâu:
- **Multimodal Engine (Phân tích Đa phương thức):** Tải video dạng MP4 xuống để phân tích.
  - *Audio:* Sử dụng model **Whisper** để bóc băng âm thanh (Speech-to-Text).
  - *Vision:* Dùng **EasyOCR** để đọc chữ trên video và **BLIP** để mô tả bối cảnh hình ảnh (Image Captioning).
  - *Synthesis:* Đẩy toàn bộ text thô lấy được vào cho LLM (dùng **Ollama Llama 3** nếu chạy local hoặc qua **Groq API** nếu hoạt động trên cloud/Modal) để tóm tắt và đánh giá ngữ cảnh video.
- **Categorization & Sentiment (Phân loại & Cảm xúc):** 
  - Sử dụng Zero-shot classification (mDeBERTa) kết hợp Multi-label logic để phân loại chủ đề (tối đa 3 danh mục/video). 
  - Phân tích cảm xúc từ top comment.
- **Viral Prediction (Dự báo Viral):** Đưa các chỉ số đánh giá và vận tốc tương tác (Viral Velocity) vào mô hình **Random Forest Classifier** (`scikit-learn`) để dự báo xác suất video chuẩn bị viral hay không. Xử lý hạ tầng chạy AI này có thể được scale bằng **Modal** để tận dụng GPU đám mây.

### 3. Dashboard (Bảng điều khiển Trực quan) - `src/dashboard/`
- **Công nghệ:** Streamlit.
- **Chức năng:** Kết nối với Supabase để kéo các video đã được gán nhãn, trình bày biểu đồ (Radar, Line chart) phân tích xu hướng và hiển thị tốc độ Viral Velocity (Tốc độ lan truyền). 

## ⚙️ Cấu trúc thư mục (Directory Structure)

```text
TrendSense/
├── .github/workflows/    // File YAML chạy GitHub Actions cho Scraping
├── config/               // Cấu hình tập trung `settings.py` (load từ .env)
├── data/                 // Lưu trữ models Random Forest (.joblib) & file MP4 tải tạm
├── src/                  // Source code chính
│   ├── scraper/          // Code cho bot thu thập của ChromeDriver
│   ├── ai_core/          // Khối trí tuệ nhân tạo tính toán và dự đoán
│   └── dashboard/        // Giao diện web báo cáo Streamlit
├── plan.md               // Plan cũ
├── project.md            // (File tổng kết hiện tại)
├── requirements*.txt     // Phân tách thư viện (cho Actions và local)
└── run.py                // Entrypoint để chạy từ đầu đến cuối 3 module (Scraper -> AI -> Dashboard) nội bộ
```

## 🚀 Đặc điểm kỹ thuật nổi bật
- **Tiêu chí lan truyền độc quyền:** Sử dụng công thức Viral Velocity `(Views/Giờ × Engagement Rate) / log₁₀(Tuổi Video + 10)` làm nền tảng đánh giá.
- **Serverless AI Model:** Quá trình phân tích GPU nặng có thể spin-up linh hoạt thông qua webhook của API [Modal.com] thay vì bắt buộc chạy ở máy tính nội bộ.
- **Quản lý Vòng đợi (Queueing):** Hệ thống không phân tích ngay khi cào, mà đổ vào Database. Khối AI chỉ tập trung chạy cronjob xử lý các video chưa qua xử lý giúp giảm thiểu tài nguyên và tránh rủi ro treo hệ thống do quá tải bộ nhớ.
