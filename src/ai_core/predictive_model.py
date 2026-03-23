import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Gọi Trạm điều phối (Nếu cậu đã setup settings.py, nếu chưa thì tự gõ đường dẫn cứng vào)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

print("\n[🚀] KHỞI ĐỘNG MÔ HÌNH DỰ BÁO XU HƯỚNG TƯƠNG LAI...")

# 1. ĐỌC DỮ LIỆU ĐÃ PHÂN TÍCH
data_path = settings.PROCESSED_FILE
if not os.path.exists(data_path):
    print("[!] Không tìm thấy dữ liệu. Phải chạy nlp_model.py trước.")
    exit()

df = pd.read_csv(data_path)

# Lọc bỏ các dòng rác không có View
df = df[df['Views'] > 0].copy()

# 2. FEATURE ENGINEERING (CHẾ TẠO CHỈ SỐ LÕI)
# Tuyệt đối không nạp số View/Like thô vào AI, phải biến thành Tỷ lệ (%)
df['Like_Rate'] = df['Likes'] / df['Views']
df['Comment_Rate'] = df['Comments'] / df['Views']
df['Share_Rate'] = df['Shares'] / df['Views']
df['Save_Rate'] = df['Saves'] / df['Views']

# Xử lý các giá trị rỗng nếu có
features = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']
df[features] = df[features].fillna(0)

# 3. GẮN NHÃN MỤC TIÊU (LABELING)
# Thuật toán: Top 20% video có Trend_Score cao nhất lịch sử được gắn nhãn 1 (Siêu Trend), còn lại là 0
threshold = df['Trend_Score'].quantile(0.80)
df['Is_Future_Trend'] = (df['Trend_Score'] >= threshold).astype(int)

# 4. CHIA TẬP HUẤN LUYỆN
X = df[features]
y = df['Is_Future_Trend']

# Dùng 80% data để dạy AI, 20% để kiểm tra độ khôn của nó
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# 5. HUẤN LUYỆN MÔ HÌNH (TRAINING)
print("[*] Đang ép AI học các mẫu tương tác ngầm...")
rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
rf_model.fit(X_train, y_train)

# Kiểm tra độ chính xác nhanh
y_pred = rf_model.predict(X_test)
print("\n📊 BÁO CÁO ĐỘ CHÍNH XÁC (TESTING):")
print(classification_report(y_test, y_pred, target_names=['Bình thường', 'SẼ THÀNH TREND']))

# 6. DỰ ĐOÁN THỰC TẾ TRÊN TOÀN BỘ DATA
# Tính ra xác suất % bùng nổ của từng video
probabilities = rf_model.predict_proba(X)[:, 1] 
df['Viral_Probability_%'] = np.round(probabilities * 100, 2)

# Sắp xếp lại và lưu file (ghi đè cột dự đoán mới vào file cũ)
df_final = df.sort_values(by='Viral_Probability_%', ascending=False)
df_final.to_csv(data_path, index=False, encoding='utf-8-sig')

print(f"\n[*] XONG! Đã cấy thành công cột 'Viral_Probability_%' vào dữ liệu.")
print("[*] Giờ chỉ việc mở Dashboard lên để xem video nào sắp nổ tung!")