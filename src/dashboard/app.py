import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sys

# Khai báo cho Python biết thư mục gốc ở đâu để import file settings
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# ==========================================
# PHẦN 1: CẤU HÌNH GIAO DIỆN & ĐƯỜNG DẪN
# ==========================================
st.set_page_config(page_title="TrendSense Radar", page_icon="🎯", layout="wide")

DATA_FILE = settings.PROCESSED_FILE

st.title("🎯 TrendSense Radar: Hệ Thống Dự Báo Viral AI")
st.markdown("Phân tích chỉ số tương tác và dự báo xác suất bùng nổ của các video ngắn.")

# ==========================================
# PHẦN 2: TẢI VÀ LÀM SẠCH DỮ LIỆU
# ==========================================
@st.cache_data
def load_data():
    if not os.path.exists(DATA_FILE):
        return None
    df = pd.read_csv(DATA_FILE, low_memory=False)
    
    # 1. Xử lý "Không có tiêu đề": Lấy ID video từ Link
    def extract_id(link):
        if not isinstance(link, str) or 'video/' not in link:
            return "Video Khuyết Danh"
        return "ID: " + link.split('video/')[-1].split('?')[0][:10] + "..."

    df['Display_Name'] = df['Caption'].apply(lambda x: str(x)[:40] + "..." if pd.notna(x) and str(x).strip() != "" else None)
    df['Display_Name'] = df['Display_Name'].fillna(df['Link'].apply(extract_id))
    
    # Tạo text để chèn link bấm được vào biểu đồ
    df['Clickable_Name'] = df.apply(lambda row: f"<a href='{row['Link']}'>{row['Display_Name']}</a>", axis=1)

    # 2. Đảm bảo có cột Xác suất (Nếu người dùng chưa chạy file dự đoán)
    if 'Viral_Probability_%' not in df.columns:
        df['Viral_Probability_%'] = 0.0
        
    return df

df = load_data()

if df is None or df.empty:
    st.warning("⚠️ Chưa có dữ liệu! Cậu hãy chạy luồng cào data và huấn luyện AI trước nhé.")
    st.stop()

# ==========================================
# PHẦN 3: TỔNG QUAN CHỈ SỐ (METRICS)
# ==========================================
st.divider()
st.subheader("📊 Trạm Quan Trắc Tương Tác")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Tổng Số Video Đang Theo Dõi", f"{len(df):,}")
with col2:
    st.metric("Tổng Lượt Xem Hệ Sinh Thái", f"{int(df['Views'].sum()):,}")
with col3:
    st.metric("Tổng Lượt Tim Mạng Lưới", f"{int(df['Likes'].sum()):,}")
with col4:
    # Đếm số video có tỷ lệ viral cao (> 50%)
    viral_videos = len(df[df['Viral_Probability_%'] > 50])
    st.metric("🔥 Mầm Mống Viral Phân Tích Được", viral_videos)

# ==========================================
# PHẦN 4: BIỂU ĐỒ TRỰC QUAN AI
# ==========================================
st.divider()

# HÀNG 1: DỰ BÁO XU HƯỚNG
st.subheader("🚀 Top 15 Video Có Xác Suất Viral Cao Nhất")
st.caption("AI học từ tương tác ngầm để chỉ ra những video có tiềm năng bùng nổ trong tương lai.")

top_viral = df.sort_values(by="Viral_Probability_%", ascending=False).head(15)

# Đổi màu biểu đồ dựa trên tỷ lệ Viral
fig_viral = px.bar(
    top_viral, 
    x="Viral_Probability_%", 
    y="Clickable_Name", 
    orientation='h',
    color="Viral_Probability_%",
    color_continuous_scale="Reds", 
    hover_data=["Views", "Likes", "Trend_Score"],
    text="Viral_Probability_%"
)
fig_viral.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig_viral.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
st.plotly_chart(fig_viral, use_container_width=True)


# HÀNG 2: BÓC TÁCH CÔNG THỨC VIRAL (SCATTER PLOT)
st.divider()
colA, colB = st.columns([2, 1])

with colA:
    st.subheader("Bản Đồ Phân Bổ: Tim vs Xem vs Xác Suất Viral")
    st.caption("Khám phá xem video cần bao nhiêu Tim và Xem để lọt vào 'Vùng Đỏ' (Viral).")
    
    # Lọc bỏ nhiễu: Chỉ vẽ những video có View từ trung bình trở lên để nhìn rõ
    min_views_to_show = df['Views'].quantile(0.2)
    df_scatter = df[df['Views'] > min_views_to_show]

    fig_scatter = px.scatter(
        df_scatter, 
        x="Views", 
        y="Likes", 
        color="Viral_Probability_%",
        size="Comments",  # Bong bóng to hay nhỏ dựa vào Comment
        hover_name="Display_Name",
        log_x=True, log_y=True, # Dùng thang logarit để dễ nhìn do chênh lệch View quá lớn
        color_continuous_scale="Turbo"
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with colB:
    st.subheader("Tỷ Trọng Cảm Xúc (NLP)")
    if len(df[df['Video_Sentiment'] != "⚪ KHÔNG CÓ BÌNH LUẬN"]) > 0:
        sentiment_counts = df['Video_Sentiment'].value_counts().reset_index()
        sentiment_counts.columns = ['Video_Sentiment', 'Count']
    
        fig_pie = px.pie(
            sentiment_counts, 
            values='Count', 
            names='Video_Sentiment', 
            hole=0.4,
            color='Video_Sentiment',
            color_discrete_map={
                "🟢 TÍCH CỰC": "#00CC96",
                "🔴 TIÊU CỰC / TRANH CÃI": "#EF553B",
                "🟡 TRUNG LẬP": "#FFA15A",
                "⚪ KHÔNG CÓ BÌNH LUẬN": "#333333" # Đổi màu xám tối cho đỡ chói mắt
            }
        )
        fig_pie.update_layout(showlegend=False) # Ẩn legend cho gọn vì chữ đã nằm trên bánh
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("💡 Bộ dữ liệu hiện tại tập trung vào chỉ số tương tác, không có dữ liệu văn bản để AI phân tích cảm xúc.")

# ==========================================
# PHẦN 5: DỮ LIỆU ĐÀO SÂU DÀNH CHO NGƯỜI QUẢN TRỊ
# ==========================================
st.divider()
with st.expander("📋 Xem dữ liệu chiến lược chi tiết (Bảng Raw Data)"):
    display_cols = ['Link', 'Viral_Probability_%', 'Trend_Score', 'Video_Sentiment', 'Views', 'Likes', 'Comments', 'Shares', 'Saves', 'Display_Name']
    valid_cols = [col for col in display_cols if col in df.columns]
    
    # Định dạng lại bảng cho đẹp
    st.dataframe(
        df[valid_cols].sort_values(by="Viral_Probability_%", ascending=False),
        column_config={
            "Viral_Probability_%": st.column_config.ProgressColumn(
                "Tỷ lệ Viral",
                help="Xác suất video sẽ trở thành xu hướng dựa trên AI",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
            "Link": st.column_config.LinkColumn("Nguồn Video")
        },
        use_container_width=True,
        hide_index=True
    )