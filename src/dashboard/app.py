import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from collections import Counter
from underthesea import word_tokenize
from keybert import KeyBERT
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
    hot_videos = len(df[df['Video_Sentiment'] == "🟢 TÍCH CỰC"])
    st.metric("Video Tích cực", hot_videos)

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
                         "🟢 TÍCH CỰC": "#00CC96",
                         "🔴 TIÊU CỰC / TRANH CÃI": "#EF553B",
                         "🟡 TRUNG LẬP": "#FFA15A",
                         "⚪ KHÔNG CÓ BÌNH LUẬN": "#888888"
                     })
    st.plotly_chart(fig_pie, use_container_width=True)

with colB:
    st.subheader("Top 10 Video Sức Hút Khủng Nhất (Trend Score)")
    # Sắp xếp theo Trend_Score thay vì Likes như cũ
    top_videos = df.sort_values(by="Trend_Score", ascending=False).head(10)
    
    # 1. Cắt ngắn Caption để biểu đồ không bị tràn
    top_videos['Short_Caption'] = top_videos['Caption'].apply(lambda x: str(x)[:30] + "..." if pd.notna(x) else "Không có tiêu đề")
    
    # 2. THUẬT TOÁN MỚI: Ép thẻ HTML để biến text thành Link bấm được
    top_videos['Clickable_Caption'] = top_videos.apply(lambda row: f"<a href='{row['Link']}'>{row['Short_Caption']}</a>", axis=1)
    
    # 3. Đổi trục y thành Clickable_Caption và ném thêm "Link" vào hover_data để hiển thị khi rê chuột
    fig_bar = px.bar(top_videos, x="Trend_Score", y="Clickable_Caption", orientation='h',
                     color="Video_Sentiment", hover_data=["Views", "Likes", "Comments", "Link"],
                     text="Trend_Score")
                     
    fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PHẦN 5: AI TRÍCH XUẤT CỤM TỪ TRENDING (KeyBERT)
# ==========================================
st.divider()
st.subheader("🏷️ Top Cụm Từ Trending (KeyBERT AI)")
st.caption("Sử dụng mô hình Transformer để phân tích ngữ nghĩa và bốc tách các cụm từ cốt lõi.")

# Tải mô hình AI đa ngôn ngữ (Cache lại để web không tải lại từ đầu mỗi lần F5)
@st.cache_resource
def load_kw_model():
    # Dùng model MiniLM siêu nhẹ, hỗ trợ hơn 50 ngôn ngữ (có Tiếng Việt)
    return KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')

kb_model = load_kw_model()

# Bộ lọc rác (Giữ nguyên)
stop_words = [
    'và', 'là', 'có', 'không', 'thì', 'mà', 'của', 'cho', 'với', 'để', 'một', 'những', 'các', 'cái', 'này', 'kia', 'rồi', 'như', 'được', 'trong', 'đã', 'đang', 'sẽ', 'nào', 'ai', 'gì', 'nha', 'nhé', 'ạ', 'ơi', 'đâu', 'đó', 'thế', 'ra', 'vào', 'lại', 'đi', 'đến', 'từ', 'người', 'mình', 'bạn', 'em', 'anh', 'chị', 'nó', 'tao', 'mày', 'video', 'clip', 'xem', 'nhiều', 'lắm', 'quá', 'thật', 'nữa', 'thôi', 'luôn', 'vậy', 'nhưng', 'khi', 'nếu', 'hay', 'còn', 'sao', 'cũng', 'con', 'ông', 'thấy', 'tôi', 'hết', 'phải', 'nhìn', 'chưa', 'tui', 'mới', 'làm', 'biết', 'chứ', 'đấy', 'cứ', 'lên', 'xuống', 'qua', 'thằng', 'bà', 'nói', 'đây', 'thích', 'the', 'this', 'is', 'you', 'for', 'that', 'how', 'que', 'and', 'with', 'my', 'in', 'of', 'it', 'to', 'on', 'me', 'sticker', 'fyp', 'viral', 'xuhuong', 'tiktok', 'trend', 'trending', 'capcut', 'xhtiktok', 'foryou', 'nhạc'
]

# Gom chữ
text_data = ""
if 'Caption' in df.columns:
    text_data += " ".join(df['Caption'].dropna().astype(str)) + " "
    
for i in range(1, 11):
    col = f'Top{i}_Cmt'
    if col in df.columns:
        text_data += " ".join(df[col].dropna().astype(str)) + " "

# Dọn dẹp text thô
text_data = str(text_data).lower()
text_data = re.sub(r'http\S+', '', text_data) 
text_data = re.sub(r'[^\w\s\u0102-\u1EF9]', ' ', text_data) 

if len(text_data.split()) > 10:
    with st.spinner('AI đang quét ngữ nghĩa để tìm từ khóa...'):
        # CHÌA KHÓA NẰM Ở ĐÂY: Dùng KeyBERT để bốc từ
        # keyphrase_ngram_range=(2,3) nghĩa là chỉ lấy cụm từ có 2 đến 3 chữ
        keywords = kb_model.extract_keywords(text_data, 
                                             keyphrase_ngram_range=(2, 3), 
                                             stop_words=stop_words, 
                                             top_n=15, 
                                             use_mmr=True, diversity=0.3) # Dùng MMR để các từ khóa đa dạng, không bị trùng lặp ý nghĩa

    if keywords:
        # keywords trả về dạng list chứa tuple [('từ khóa 1', điểm_số), ('từ khóa 2', điểm_số)]
        df_words = pd.DataFrame(keywords, columns=['Cụm từ', 'Độ chuẩn xác (Relevance)'])
        
        fig_words = px.bar(df_words, x='Độ chuẩn xác (Relevance)', y='Cụm từ', orientation='h',
                           color='Độ chuẩn xác (Relevance)', color_continuous_scale='Teal',
                           text='Độ chuẩn xác (Relevance)')
        fig_words.update_traces(texttemplate='%{text:.2f}', textposition='outside')
        fig_words.update_layout(yaxis={'categoryorder':'total ascending'}) 
        
        st.plotly_chart(fig_words, use_container_width=True)
    else:
        st.info("Không tìm thấy cụm từ nổi bật.")
else:
    st.info("Chưa có đủ dữ liệu chữ để phân tích cụm từ.")
# ==========================================
# PHẦN 6: DỮ LIỆU THÔ DÀNH CHO CHUYÊN GIA
# ==========================================
with st.expander("📋 Xem dữ liệu chi tiết (Raw Data)"):
    display_cols = ['Link', 'Trend_Score', 'Video_Sentiment', 'Views', 'Likes', 'Caption']
    # Chỉ hiển thị các cột tồn tại trong file để tránh lỗi
    valid_cols = [col for col in display_cols if col in df.columns]
    st.dataframe(df[valid_cols].sort_values(by="Trend_Score", ascending=False))