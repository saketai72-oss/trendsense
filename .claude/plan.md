# Kế hoạch Mở rộng: Tính năng Dự báo Video Người dùng

Tính năng này mở rộng nền tảng thành một công cụ tư vấn trực tiếp, cho phép người dùng đưa video của riêng họ (upload trực tiếp hoặc chèn link TikTok) để được AI đánh giá và dự báo khả năng lan truyền.

### A. Trải nghiệm người dùng trên Dashboard (Streamlit)
1. **Khu vực Input**: Giao diện (UI) bổ sung form để người dùng dán URL TikTok hoặc khối Upload trực tiếp file video MP4.
2. **Xử lý On-Demand**: 
   - Giao diện sẽ gọi **Modal API** ngay lập tức để xử lý video này độc lập với luồng cào dữ liệu định kỳ.

### B. Quy trình nhận diện và Dự báo
1. **Phân tích Thực tế (Multimodal AI)**: 
   - Modal API chạy Whisper (bóc giọng nói), BLIP (phân tích hình ảnh), EasyOCR (đọc text trên màn hình) để hiểu toàn diện nội dung video của người dùng.
2. **Dự đoán bằng Machine Learning**:
   - Chạy dữ liệu phân tích qua mô hình **RandomForest** hoặc suy luận qua **Groq API (Llama 3)** để tính ra điểm % (Xác suất Viral / Viral Probability).

### C. Báo cáo Đầu ra (Output)
Dashboard sẽ render kết quả trả về bao gồm 3 thành phần siêu giá trị:
1. **Mô tả video chi tiết**: AI tóm tắt tự động hình ảnh, kịch bản, âm thanh và thông điệp mà video đang truyền tải.
2. **Báo cáo Dự đoán (Prediction Result)**: Điểm số hoặc Phần trăm bùng nổ (Thấp / Trung bình / Cao / Đột phá).
3. **Đề xuất Tối ưu (Actionable Recommendations)**: Groq AI sẽ sinh ra các lời khuyên chuyên sâu để tinh chỉnh video giúp tăng level "xu hướng":
   - **Tối ưu Hook**: Cải thiện 3 giây đầu tiên để giữ chân người xem.
   - **Gợi ý Âm thanh**: Đề xuất nhạc nền đang trending phù hợp với ngữ cảnh.
   - **Tối ưu Caption & Hashtags**: Viết lại caption chuẩn SEO TikTok và đi kèm hashtag tiềm năng.
   - **Nhịp độ & CTA**: Lời khuyên về cách cắt dựng và kêu gọi hành động (Call To Action).

---

## 2. Kế hoạch Tái cấu trúc Hệ thống & Nâng cấp Giao diện (React Frontend)

Hệ thống sẽ được đập đi xây lại cấu trúc thư mục nhằm tách biệt rõ ràng Frontend và Backend. Giao diện cũ bằng Streamlit sẽ bị loại bỏ, thay vào đó Frontend sẽ được viết mới hoàn toàn bằng **React** (với Next.js và Tailwind CSS), sử dụng **AJAX** để có trải nghiệm SPA mượt mà.

### A. Tái cấu trúc Thư mục Hệ thống
Hệ thống sẽ được chia thành hai nhánh lớn:
- **`backend/`**: Chứa toàn bộ AI Core, quy trình Cào dữ liệu (Scraper), Modal API, tương tác Supabase Database và Machine Learning Models. File API endpoint sẽ cung cấp dữ liệu cho phía trước.
- **`frontend/`**: Chứa toàn bộ Application React phục vụ người dùng.

### B. Xây dựng Frontend UI/UX (Theo phong cách Crypto Dashboard)
Giao diện sẽ được thiết kế dựa trên hình mẫu Crypto Landing Page (Dark mode, neon purple/blue accents, Glassmorphism, phong cách hiện đại và huyền bí).

1. **Hero Section & Navigation**: Thanh điều hướng trên cùng chuyên nghiệp với các nút Call To Action (Ví dụ: Sign In/Dashboard). Phần Banner (Hero) nhấn mạnh công cụ "Dự báo Xu hướng TikTok với AI".
2. **Khu vực Tương tác (User Video Input)**: Tính năng nhập URL TikTok hoặc tải video sẽ được thiết kế mượt mà dưới dạng các Form Card giống như đăng ký tài khoản hoặc "Add Funds" của sàn Crypto.
3. **Data Table thông minh (AJAX + Phân trang)**:
   - Mô phỏng theo bảng "Market Trend Live Stream" của các sàn điện tử.
   - Bảng hiển thị danh sách video đang trending hiện tại.
   - Các cột: Thumbnails/Tên Video, Tốc độ Viral (thay cho giá), Mức độ Bùng nổ dự báo (thay cho Change 24H), Tương tác tổng, và nút "Xem phân tích chuyên sâu".
   - Tích hợp **Phân trang (Pagination)** và **Lọc thông minh (Smart Filtering)** qua AJAX để tìm kiếm video theo hashtag, chủ đề hoặc mức độ viral mà không cần tải lại luồng trang.
4. **Trang báo cáo Video & Recommendations**: Giao diện hiển thị các thẻ phân tích (Card Layout) tương tự như các thẻ mô tả tính năng "Secure Storage" hay phần câu hỏi thường gặp (FAQ) để render phần đánh giá AI (Hook, Cảm xúc âm thanh, và Đề xuất lên xu hướng).
