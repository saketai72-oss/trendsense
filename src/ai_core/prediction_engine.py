import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def run_viral_prediction(df):
    print("\n[🚀] KHỞI ĐỘNG MÔ HÌNH DỰ BÁO XU HƯỚNG TƯƠNG LAI...")

    # 1. Làm sạch dữ liệu đầu vào
    df = df[df['Views'] > 0].copy()

    if len(df) < 5:
        print(f"[!] ⚠️ Dữ liệu quá ít ({len(df)} video). AI cần ít nhất 5-10 video để phân tích.")
        print(" 👉 Bỏ qua bước dự đoán. Sẽ lưu dữ liệu cơ bản.")
        return df

    # 2. Feature Engineering
    df['Like_Rate'] = df['Likes'] / df['Views']
    df['Comment_Rate'] = df['Comments'] / df['Views']
    df['Share_Rate'] = df['Shares'] / df['Views']
    df['Save_Rate'] = df['Saves'] / df['Views']

    df.replace([np.inf, -np.inf], 0, inplace=True)

    features = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Positive_Score', 'Views_Per_Hour']
    df[features] = df[features].fillna(0)

    # 3. Gắn nhãn mục tiêu (Sử dụng Viral_Velocity thay cho Trend_Score cũ)
    threshold = df['Viral_Velocity'].quantile(0.80)
    if threshold <= 0: threshold = 0.001 

    df['Is_Future_Trend'] = (df['Viral_Velocity'] >= threshold).astype(int)

    if len(df['Is_Future_Trend'].unique()) < 2:
        print("[!] ⚠️ Dữ liệu chưa đủ độ phân hoá (toàn video flop hoặc toàn video siêu trend).")
        print("[*] AI gán tỷ lệ bùng nổ mặc định là 5.0%.")
        df['Viral_Probability_%'] = 5.0
        return df

    # 4. Huấn luyện mô hình
    X = df[features]
    y = df['Is_Future_Trend']

    try:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        print(f"[*] Đang huấn luyện AI ngầm trên {len(X_train)} mẫu...")
        
        rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
        rf_model.fit(X_train, y_train)
        y_pred = rf_model.predict(X_test)
        
        if len(y_test.unique()) == 2:
            print("\n📊 BÁO CÁO ĐỘ CHÍNH XÁC (TESTING):")
            print(classification_report(y_test, y_pred, target_names=['Bình thường', 'SẼ THÀNH TREND'], zero_division=0))
            
    except ValueError:
        print("[!] ⚠️ Tập dữ liệu nhỏ, AI học nén trên toàn bộ dữ liệu (không qua test).")
        rf_model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
        rf_model.fit(X, y)

    # 5. Dự đoán và xuất kết quả
    probabilities = rf_model.predict_proba(X)[:, 1] 
    df['Viral_Probability_%'] = np.round(probabilities * 100, 2)

    print("[*] XONG! Đã cấy thành công cột 'Viral_Probability_%' vào dữ liệu.")
    
    # Dọn dẹp bớt các cột trung gian không cần thiết xuất ra CSV (tuỳ chọn)
    cols_to_drop = ['Like_Rate', 'Comment_Rate', 'Share_Rate', 'Save_Rate', 'Is_Future_Trend']
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

    # Trả về dataframe đã sắp xếp theo tỷ lệ viral giảm dần
    return df.sort_values(by='Viral_Probability_%', ascending=False)