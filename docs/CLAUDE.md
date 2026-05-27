# ==========================================
# AGENTS.md — HƯỚNG DẪN ĐỒNG BỘ THÔNG MINH
# ==========================================
# Hãy đọc kỹ và làm theo.
# Đây là hướng dẫn quan trọng để AI làm việc hiệu quả trên dự án này.

# --- PHẦN 1: QUY TẮC CHUNG ---
# 1. Luôn giữ ý tưởng đơn giản, dễ triển khai, không làm mọi thứ phức tạp.
# 2. Ưu tiên tối ưu, refactor code cũ trước khi thêm tính năng mới.
# 3. Trước khi làm, hãy phân tích: "Làm sao để tối ưu code?" thay vì "Làm sao để làm xong?".
# 4. Luôn kiểm tra kết quả sau mỗi lần thay đổi.
# 5. Không thay đổi cấu hình (CONFIG/ENV/SETTINGS) trừ khi được cho phép.
# 6. Khi code bị lỗi hoặc không chạy, hãy tìm root cause trước khi sửa.

# --- PHẦN 2: CÁC VẤN ĐỀ CẦN FIX ---
# 1. Tối ưu UI: Luôn giữ theme đơn giản, tránh màu mè, hiệu ứng rườm rà. Ưu tiên UX/UI nhẹ, dễ nhìn, không làm loạn mắt người dùng.
# 2. UI cho Mobile: Đảm bảo tất cả tính năng hiển thị tốt trên mobile. Các thanh điều hướng và nút bấm cần dễ thao tác trên màn hình nhỏ.
# 3. Cấu hình Backend: Cài đặt và cấu hình backend phải tự động, không cần manual setup. Đảm bảo các service (Redis, Model Workers) tự start và cấu hình đúng.
# 4. Cấu hình Redis: Tối ưu Redis cho phù hợp với RAM máy (2-4GB). Giới hạn `maxmemory` hợp lý để tránh treo máy.
# 5. Tối ưu Performance: Đảm bảo các tác vụ nặng (phân tích video, LLM) chạy song song hiệu quả. Nếu cần, hãy sử dụng Worker/Queue để tối ưu tải máy.

# --- PHẦN 3: CÁC TÍNH NĂNG CẦN LÀM ---
# 1. Upload & Share: Phải có tính năng upload video dễ dùng và dễ chia sẻ.
# 2. Dark Mode: Ưu tiên triển khai Dark Mode sớm vì nó quan trọng với trải nghiệm người dùng, giúp hạn chế mỏi mắt khi dùng vào buổi tối.
# 3. Notification System: Cần hệ thống thông báo nội bộ (in-app notifications).
# 4. Admin Panel: Cần giao diện quản trị để quản lý dự án và thông tin.
# 5. Model Monitoring: Giao diện theo dõi tình trạng các AI model (Whisper, OCR, BLIP, Ollama).

# --- PHẦN 4: KẾT NỐI & TÍNH TOÀN VẸN CỦA DỰ ÁN ---
# 1. Đảm bảo Frontend và Backend có thể giao tiếp đầy đủ, không có lỗi 404 hoặc CORS.
# 2. Kiểm tra API endpoint và response hợp lệ.
# 3. Đảm bảo không có lỗi 500 từ AI Engine (Phân tích video, LLM, etc.).
# 4. Chạy thử với file video mẫu để đảm bảo tính năng phân tích hoạt động đầy đủ (Audio, OCR, Image).
# 5. Đảm bảo tính năng chia sẻ (Share) không bị lỗi.

# --- PHẦN 5: CÁC TÍNH NĂNG ĐÃ TÌM THẤY TRONG PROJECT ---
# Các tính năng này đã được phát hiện từ các file code:

# ✅ UI Features:
# 1. Auto‑dark mode detection
# 2. Admin Dashboard
# 3. Share & Embed Video
# 4. Video Analytics
# 5. Comment Sentiment
# 6. Category Prediction
# 7. Duplicate Video Detection
# 8. Content Labeling
# 9. Real‑time Status
# 10. Trending Score
# 11. AI Worker Monitoring
# 12. Video Download
# 13. Video Transcription
# 14. Trend History
# 15. Comment Analyzer
# 16. Trending Time Display
# 17. Engagement Metrics
# 18. Upload & Share System
# 19. Category Dashboard
# 20. Video Detail Page

# ✅ Backend & AI Features:
# 1. Trend Prediction Model (Random Forest)
# 2. Multimodal Analysis (Audio + OCR + Vision)
# 3. Whisper (Audio-to-Text)
# 4. EasyOCR (Text Extraction)
# 5. BLIP (Image Captioning)
# 6. LLM Integration (Ollama)
# 7. Video Processing Pipeline
# 8. Redis Job Queue
# 9. Category Classifier
# 10. Sentiment Analysis
# 11. Video Deduplication
# 12. Content Rating

# ✅ Database Models:
# 1. VideoInfoModel
# 2. TrendingVideoModel
# 3. TrendingScoreModel
# 4. VideoProcessingModel
# 5. CategoryModel
# 6. TrendHistoryModel
# 7. UserActivityModel
# 8. ContentQualityModel
# 9. ModelMetricsModel

# Hãy sử dụng các tính năng đã có để xây dựng và tối ưu dự án.
