import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from collections import Counter
from underthesea import word_tokenize

# ==========================================
# PHẦN 1: CẤU HÌNH GIAO DIỆN & ĐƯỜNG DẪN
# ==========================================
st.set_page_config(page_title="TrendSense AI", page_icon="📈", layout="wide")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR)) 
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "processed", "tiktok_analyzed.csv")

st.title("📈 TrendSense: Hệ Thống Phát Hiện Xu Hướng AI")
st.markdown("Hệ thống tự động cào dữ liệu, phân tích cảm xúc và trích xuất từ khóa Trending.")

# ==========================================
# PHẦN 2: TẢI VÀ KIỂM TRA DỮ LIỆU
# ==========================================
@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        return None
    df = pd.read_csv(DATA_FILE)
    return df

df = load_data()

if df is None or df.empty:
    st.warning("⚠️ Chưa có dữ liệu! Cậu hãy chạy bot cào (apify_bot.py) và AI (nlp_model.py) trước nhé.")
    st.stop()

# ==========================================
# PHẦN 3: TỔNG QUAN CHỈ SỐ (METRICS)
# ==========================================
st.divider()
st.subheader("📊 Tổng quan Dữ liệu")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Tổng số Video cào", f"{len(df):,}")
with col2:
    st.metric("Tổng lượt Xem (Views)", f"{int(df['Views'].sum()):,}")
with col3:
    st.metric("Tổng lượt Tim (Likes)", f"{int(df['Likes'].sum()):,}")
with col4:
    hot_videos = len(df[df['Video_Sentiment'] == "🔥 HOT & TÍCH CỰC"])
    st.metric("Video Tích cực / HOT 🔥", hot_videos)

# ==========================================
# PHẦN 4: BIỂU ĐỒ TRỰC QUAN
# ==========================================
st.divider()
colA, colB = st.columns(2)

with colA:
    st.subheader("Bức tranh Cảm xúc Cộng đồng")
    sentiment_counts = df['Video_Sentiment'].value_counts().reset_index()
    sentiment_counts.columns = ['Video_Sentiment', 'Count']
    
    fig_pie = px.pie(sentiment_counts, values='Count', names='Video_Sentiment', hole=0.4,
                     color='Video_Sentiment',
                     color_discrete_map={
                         "🔥 HOT & TÍCH CỰC": "#00CC96",
                         "⚠️ TRANH CÃI / TIÊU CỰC": "#EF553B",
                         "BÌNH THƯỜNG": "#636EFA",
                         "KHÔNG ĐỦ DỮ LIỆU": "#888888"
                     })
    st.plotly_chart(fig_pie, use_container_width=True)

with colB:
    st.subheader("Top 10 Video Sức Hút Khủng Nhất (Trend Score)")
    # Sắp xếp theo Trend_Score thay vì Likes như cũ
    top_videos = df.sort_values(by="Trend_Score", ascending=False).head(10)
    
    # Cắt ngắn Caption để biểu đồ không bị tràn
    top_videos['Short_Caption'] = top_videos['Caption'].apply(lambda x: str(x)[:30] + "..." if pd.notna(x) else "Không có tiêu đề")
    
    fig_bar = px.bar(top_videos, x="Trend_Score", y="Short_Caption", orientation='h',
                     color="Video_Sentiment", hover_data=["Views", "Likes", "Comments"],
                     text="Trend_Score")
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PHẦN 5: AI TRÍCH XUẤT TỪ KHÓA (NLP)
# ==========================================
st.divider()
st.subheader("🏷️ Top Từ Khóa & Cụm Từ Trending")
st.caption("AI sử dụng mô hình NLP Tiếng Việt gộp các từ có nghĩa từ Caption và Top 10 Comment.")

stop_words = {
    'và', 'là', 'có', 'không', 'thì', 'mà', 'của', 'cho', 'với', 'để', 
    'một', 'những', 'các', 'cái', 'này', 'kia', 'rồi', 'như', 'được', 
    'trong', 'đã', 'đang', 'sẽ', 'nào', 'ai', 'gì', 'nha', 'nhé', 'ạ', 
    'ơi', 'đâu', 'đó', 'thế', 'ra', 'vào', 'lại', 'đi', 'đến', 'từ',
    'người', 'mình', 'bạn', 'em', 'anh', 'chị', 'nó', 'tao', 'mày',
    'video', 'clip', 'xem', 'nhiều', 'lắm', 'quá', 'thật', 'nữa',
    'thôi', 'luôn', 'vậy', 'nhưng', 'khi', 'nếu', 'hay', 'còn', 'sao', 
    'cũng', 'con', 'ông', 'thấy', 'tôi', 'hết', 'phải', 'nhìn', 'chưa', 
    'tui', 'mới', 'làm', 'biết', 'chứ', 'đấy', 'cứ', 'lên', 'xuống', 
    'qua', 'thằng', 'bà', 'nói'
}

text_data = ""
if 'Caption' in df.columns:
    text_data += " ".join(df['Caption'].dropna().astype(str)) + " "
    
# Quét đủ 10 Comment thay vì 5
for i in range(1, 11):
    col = f'Top{i}_Cmt'
    if col in df.columns:
        text_data += " ".join(df[col].dropna().astype(str)) + " "

text_data = str(text_data).lower()
text_data = re.sub(r'http\S+', '', text_data)
text_data = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text_data) 

tokenized_text = word_tokenize(text_data, format="text") 
words = tokenized_text.split()

filtered_words = []
for w in words:
    clean_w = w.replace('_', ' ') 
    if clean_w not in stop_words and not clean_w.isdigit() and len(clean_w) > 2:
        filtered_words.append(clean_w)

if filtered_words:
    word_counts = Counter(filtered_words)
    top_words = word_counts.most_common(15) 
    
    df_words = pd.DataFrame(top_words, columns=['Từ khóa', 'Tần suất'])
    
    fig_words = px.bar(df_words, x='Tần suất', y='Từ khóa', orientation='h',
                       color='Tần suất', color_continuous_scale='Sunset',
                       text='Tần suất')
    fig_words.update_layout(yaxis={'categoryorder':'total ascending'}) 
    
    st.plotly_chart(fig_words, use_container_width=True)
else:
    st.info("Chưa có đủ dữ liệu chữ để phân tích từ khóa.")

# ==========================================
# PHẦN 6: DỮ LIỆU THÔ DÀNH CHO CHUYÊN GIA
# ==========================================
with st.expander("📋 Xem dữ liệu chi tiết (Raw Data)"):
    display_cols = ['Link', 'Trend_Score', 'Video_Sentiment', 'Views', 'Likes', 'Caption']
    # Chỉ hiển thị các cột tồn tại trong file để tránh lỗi
    valid_cols = [col for col in display_cols if col in df.columns]
    st.dataframe(df[valid_cols].sort_values(by="Trend_Score", ascending=False))