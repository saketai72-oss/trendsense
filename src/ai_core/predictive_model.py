import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

print("\n[🚀] KHỞI ĐỘNG MÔ HÌNH DỰ BÁO XU HƯỚNG TƯƠNG LAI...")

# 1. ĐỌC DỮ LIỆU ĐÃ PHÂN TÍCH
data_path = settings.PROCESSED_FILE
if not os.path.exists(data_path):
    print("[!] ❌ Không tìm thấy dữ liệu. Phải chạy nlp_model.py trước.")
    exit()

df = pd.read_csv(data_path)

# 2. LÀM SẠCH VÀ BẢO VỆ DỮ LIỆU
# Lọc bỏ các dòng rác không có View để tránh lỗi chia cho 0
df = df[df['Views'] > 0].copy()

# Kiểm tra an toàn: AI cần tối thiểu "nguyên liệu" để học
if len(df) < 5:
    print(f"[!] ⚠️ Dữ liệu quá ít ({len(df)} video). AI cần ít nhất 5-10 video để phân tích.")
    print(" 👉 Hãy chạy scraper_main.py cào thêm video rồi quay lại nhé!")
    exit()

# 3. FEATURE ENGINEERING (CHẾ TẠO CHỈ SỐ LÕI)
df['Like_Rate'] = df['Likes'] / df['Views']
df['Comment_Rate'] = df['Comments'] / df['Views']
df['Share_Rate'] = df['Shares'] / df['Views']
df['Save_Rate'] = df['Saves'] / df['Views']

# Quét sạch các giá trị vô cực (Infinity) do lỗi toán học
df.replace([np.inf, -np.inf], 0, inplace=True)

features = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']
df[features] = df[features].fillna(0)

# 4. GẮN NHÃN MỤC TIÊU (LABELING)
threshold = df['Trend_Score'].quantile(0.80)

# Chống lỗi 1 chiều: Đảm bảo threshold phải lớn hơn 0 để có sự phân hoá (Trend vs Flop)
if threshold <= 0:
    threshold = 0.001 

df['Is_Future_Trend'] = (df['Trend_Score'] >= threshold).astype(int)

# Chống lỗi "AI lú": Nếu dữ liệu không có độ phân hóa (Toàn 0 hoặc Toàn 1)
if len(df['Is_Future_Trend'].unique()) < 2:
    print("[!] ⚠️ Dữ liệu chưa đủ độ phân hoá (toàn video flop hoặc toàn video siêu trend).")
    print("[*] AI tạm thời gán tỷ lệ bùng nổ mặc định là 5.0% cho đến khi có thêm dữ liệu.")
    df['Viral_Probability_%'] = 5.0
    df.to_csv(data_path, index=False, encoding='utf-8-sig')
    exit()

# 5. CHIA TẬP VÀ HUẤN LUYỆN MÔ HÌNH (TRAINING)
X = df[features]
y = df['Is_Future_Trend']

try:
    # Cố gắng chia 80-20, dùng stratify để cân bằng tỷ lệ nhãn
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    print(f"[*] Đang huấn luyện AI ngầm trên {len(X_train)} mẫu...")
    
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf_model.fit(X_train, y_train)

    y_pred = rf_model.predict(X_test)
    
    # Chỉ in báo cáo nếu tập test lấy được đủ 2 loại nhãn
    if len(y_test.unique()) == 2:
        print("\n📊 BÁO CÁO ĐỘ CHÍNH XÁC (TESTING):")
        print(classification_report(y_test, y_pred, target_names=['Bình thường', 'SẼ THÀNH TREND'], zero_division=0))
        
except ValueError:
    # Fallback: Nếu data ít quá không chia tập nổi, ép AI học trên toàn bộ dữ liệu (Overfitting tạm thời)
    print("[!] ⚠️ Tập dữ liệu nhỏ, AI sẽ học nén trên toàn bộ dữ liệu (không qua bước test).")
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf_model.fit(X, y)

# 6. DỰ ĐOÁN THỰC TẾ TRÊN TOÀN BỘ DATA
# Tính ra xác suất % bùng nổ của từng video
probabilities = rf_model.predict_proba(X)[:, 1] 
df['Viral_Probability_%'] = np.round(probabilities * 100, 2)

# Sắp xếp lại và lưu file (ghi đè cột dự đoán mới vào file cũ)
df_final = df.sort_values(by='Viral_Probability_%', ascending=False)
df_final.to_csv(data_path, index=False, encoding='utf-8-sig')

print(f"\n[*] XONG! Đã cấy thành công cột 'Viral_Probability_%' vào dữ liệu.")
print("[*] Giờ chỉ việc mở Dashboard lên để xem video nào sắp nổ tung!")