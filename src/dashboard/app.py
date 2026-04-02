import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
from collections import Counter

# Khai báo cho Python biết đường dẫn gốc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# Import database
sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
from database import init_db, get_all_analyzed_videos

# Import model info
sys.path.append(os.path.join(settings.SRC_DIR, 'ai_core'))
from model_manager import get_model_info

# ==========================================
# CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(page_title="TrendSense Radar", page_icon="🎯", layout="wide")

# Custom CSS cho giao diện premium
st.markdown("""
<style>
    /* Header gradient */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        color: white;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p { color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0; font-size: 0.95rem; }

    /* Model info badge */
    .model-badge {
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.3);
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        display: inline-block;
        margin-top: 0.5rem;
        font-size: 0.8rem;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 10px;
        padding: 1rem;
    }
    [data-testid="stMetric"] label { color: #a0aec0 !important; font-size: 0.8rem !important; }
    [data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e2e8f0 !important; }

    /* Section headers */
    .section-header {
        border-left: 4px solid #764ba2;
        padding-left: 12px;
        margin: 1.5rem 0 0.5rem 0;
    }

    /* Comment cards */
    .comment-card {
        background: #1e1e2e;
        border: 1px solid #2d2d44;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.85rem;
        line-height: 1.4;
    }
    .comment-likes {
        color: #f87171;
        font-size: 0.75rem;
        margin-top: 0.2rem;
    }

    /* Keyword tag */
    .keyword-tag {
        display: inline-block;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.78rem;
        margin: 0.15rem;
    }

    /* Video detail card */
    .video-detail-card {
        background: #1a1a2e;
        border: 1px solid #2d2d44;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
model_info = get_model_info()
model_badge = ""
if model_info:
    acc = model_info.get('accuracy', 'N/A')
    acc_str = f"{acc:.1%}" if isinstance(acc, float) else str(acc)
    model_badge = (
        f'<div class="model-badge">'
        f'🧠 Model: {model_info.get("trained_at", "N/A")[:16]} | '
        f'Accuracy: {acc_str} | '
        f'Samples: {model_info.get("training_samples", "N/A")} | '
        f'Window: {model_info.get("window_days", "N/A")} ngày</div>'
    )

st.markdown(f"""
<div class="main-header">
    <h1>🎯 TrendSense Radar</h1>
    <p>Hệ thống phân tích chỉ số tương tác và dự báo xác suất bùng nổ của video ngắn — Powered by AI</p>
    {model_badge}
</div>
""", unsafe_allow_html=True)


# ==========================================
# TẢI DỮ LIỆU TỪ SQLITE
# ==========================================
@st.cache_data(ttl=300)
def load_data():
    init_db()
    rows = get_all_analyzed_videos()
    if not rows:
        return None
    df = pd.DataFrame(rows)

    # Display Name
    def extract_id(link):
        if not isinstance(link, str) or 'video/' not in link:
            return "Video Khuyết Danh"
        return "ID: " + link.split('video/')[-1].split('?')[0][:10] + "..."

    df['Display_Name'] = df['caption'].apply(
        lambda x: str(x)[:50] + "..." if pd.notna(x) and str(x).strip() not in ["", "Không tìm thấy"] else None
    )
    df['Display_Name'] = df['Display_Name'].fillna(df['link'].apply(extract_id))

    df['Clickable_Name'] = df.apply(
        lambda row: f"<a href='{row['link']}' target='_blank'>{row['Display_Name']}</a>", axis=1
    )

    # Đảm bảo cột tồn tại
    for col in ['viral_probability', 'views_per_hour', 'engagement_rate', 'viral_velocity', 'positive_score']:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

    for col in ['views', 'likes', 'comments', 'shares', 'saves']:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    if 'category' not in df.columns:
        df['category'] = 'Chưa phân loại'
    else:
        df['category'] = df['category'].fillna('Chưa phân loại')
        
    if 'video_path' not in df.columns:
        df['has_video'] = '❌ Không'
    else:
        df['has_video'] = df['video_path'].apply(lambda x: '✅ Có' if pd.notna(x) and x != '' else '❌ Không')

    return df


df = load_data()

if df is None or df.empty:
    st.warning("⚠️ Chưa có dữ liệu! Cậu hãy chạy luồng cào data và huấn luyện AI trước nhé.")
    st.stop()


# ==========================================
# PHẦN 1: TỔNG QUAN CHỈ SỐ (METRICS)
# ==========================================
st.markdown('<div class="section-header"><h3>📊 Trạm Quan Trắc Tổng Quan</h3></div>', unsafe_allow_html=True)

row1 = st.columns(6)
with row1[0]:
    st.metric("📹 Tổng Video", f"{len(df):,}")
with row1[1]:
    st.metric("👁️ Tổng Lượt Xem", f"{int(df['views'].sum()):,}")
with row1[2]:
    st.metric("❤️ Tổng Lượt Tim", f"{int(df['likes'].sum()):,}")
with row1[3]:
    st.metric("💬 Tổng Bình Luận", f"{int(df['comments'].sum()):,}")
with row1[4]:
    st.metric("🔄 Tổng Chia Sẻ", f"{int(df['shares'].sum()):,}")
with row1[5]:
    st.metric("🔖 Tổng Lưu", f"{int(df['saves'].sum()):,}")

row2 = st.columns(4)
with row2[0]:
    viral_count = len(df[df['viral_probability'] > 50])
    st.metric("🔥 Video Tiềm Năng Viral", viral_count)
with row2[1]:
    avg_engagement = df['engagement_rate'].mean()
    st.metric("📈 Engagement Trung Bình", f"{avg_engagement:.1f}%")
with row2[2]:
    avg_vph = df['views_per_hour'].mean()
    st.metric("⚡ View/Giờ Trung Bình", f"{avg_vph:,.0f}")
with row2[3]:
    unique_dates = df['scrape_date'].nunique() if 'scrape_date' in df.columns else 0
    st.metric("📅 Số Ngày Thu Thập", unique_dates)


# ==========================================
# PHẦN 2: DỰ BÁO VIRAL — TOP 15
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>🚀 Top 15 Video Có Xác Suất Viral Cao Nhất</h3></div>', unsafe_allow_html=True)
st.caption("AI học từ tương tác ngầm (like rate, share rate, save rate, views/hour) để dự đoán tiềm năng bùng nổ.")

top_viral = df.sort_values(by="viral_probability", ascending=False).head(15)

fig_viral = px.bar(
    top_viral,
    x="viral_probability",
    y="Clickable_Name",
    orientation='h',
    color="viral_probability",
    color_continuous_scale=["#1a1a2e", "#e94560", "#ff6b6b"],
    hover_data={"views": ":,", "likes": ":,", "viral_velocity": ":.1f", "engagement_rate": ":.1f"},
    text="viral_probability",
    labels={"viral_probability": "Xác Suất Viral (%)", "Clickable_Name": ""}
)
fig_viral.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
fig_viral.update_layout(
    yaxis={'categoryorder': 'total ascending'},
    height=520,
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font_color='#a0aec0',
    coloraxis_showscale=False,
    margin=dict(l=10, r=60)
)
st.plotly_chart(fig_viral, use_container_width=True)


# ==========================================
# PHẦN 3: PHÂN TÍCH ĐA CHIỀU
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>🔬 Phân Tích Đa Chiều</h3></div>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Bản Đồ Tương Tác",
    "📊 Phân Bổ Engagement",
    "⚡ Viral Velocity",
    "📅 Timeline Thu Thập",
    "🏷️ Phân Bổ Danh Mục"
])

# --- TAB 1: Scatter Plot
with tab1:
    col_sc1, col_sc2 = st.columns([3, 1])
    with col_sc2:
        size_by = st.selectbox("Kích thước bong bóng theo:", ["comments", "shares", "saves"], index=0)
        color_by = st.selectbox("Tô màu theo:", ["viral_probability", "engagement_rate", "positive_score"], index=0)

    with col_sc1:
        min_views_to_show = df['views'].quantile(0.1)
        df_scatter = df[df['views'] > min_views_to_show].copy()

        # Đảm bảo size column không có giá trị 0 (plotly yêu cầu positive)
        df_scatter_size = df_scatter[size_by].clip(lower=1)

        fig_scatter = px.scatter(
            df_scatter,
            x="views", y="likes",
            color=color_by,
            size=df_scatter_size,
            hover_name="Display_Name",
            hover_data={"views": ":,", "likes": ":,", "comments": ":,", "shares": ":,", "engagement_rate": ":.1f"},
            log_x=True, log_y=True,
            color_continuous_scale="Turbo",
            labels={"views": "Lượt Xem", "likes": "Lượt Tim"}
        )
        fig_scatter.update_layout(
            height=500,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0'
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# --- TAB 2: Engagement Distribution
with tab2:
    col_e1, col_e2 = st.columns(2)

    with col_e1:
        fig_eng = px.histogram(
            df, x="engagement_rate", nbins=30,
            color_discrete_sequence=["#764ba2"],
            labels={"engagement_rate": "Engagement Rate (%)"},
            title="Phân Bổ Engagement Rate Toàn Bộ Video"
        )
        fig_eng.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0', showlegend=False
        )
        st.plotly_chart(fig_eng, use_container_width=True)

    with col_e2:
        # Radar chart cho video viral nhất
        if len(top_viral) > 0:
            best = top_viral.iloc[0]
            categories = ['Like Rate', 'Comment Rate', 'Share Rate', 'Save Rate', 'Positive Score']

            # Normalize tất cả về thang 0-1 so với max của dataset
            vals = []
            for col_name, db_col in [
                ('Like Rate', 'likes'), ('Comment Rate', 'comments'),
                ('Share Rate', 'shares'), ('Save Rate', 'saves')
            ]:
                rate = best[db_col] / best['views'] if best['views'] > 0 else 0
                max_rate = (df[db_col] / df['views'].clip(lower=1)).max()
                vals.append(rate / max_rate if max_rate > 0 else 0)
            vals.append(best['positive_score'] / 100 if best['positive_score'] else 0)
            vals.append(vals[0])  # Close the radar
            cats = categories + [categories[0]]

            fig_radar = go.Figure(data=go.Scatterpolar(
                r=vals, theta=cats, fill='toself',
                fillcolor='rgba(118, 75, 162, 0.3)',
                line_color='#764ba2', name=best['Display_Name'][:30]
            ))
            fig_radar.update_layout(
                polar=dict(
                    bgcolor='rgba(0,0,0,0)',
                    radialaxis=dict(visible=True, range=[0, 1], gridcolor='#2d2d44'),
                    angularaxis=dict(gridcolor='#2d2d44')
                ),
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#a0aec0', showlegend=False,
                title=f"Radar: {best['Display_Name'][:35]}"
            )
            st.plotly_chart(fig_radar, use_container_width=True)

# --- TAB 3: Viral Velocity
with tab3:
    df_vel = df[df['viral_velocity'] > 0].sort_values('viral_velocity', ascending=False).head(25)

    fig_vel = px.bar(
        df_vel,
        x="Display_Name", y="viral_velocity",
        color="viral_probability",
        color_continuous_scale=["#16213e", "#e94560"],
        labels={"viral_velocity": "Viral Velocity", "Display_Name": ""},
        title="Top 25 Video: Tốc Độ Lan Truyền (Viral Velocity)"
    )
    fig_vel.update_layout(
        xaxis_tickangle=-45, height=450,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        font_color='#a0aec0', coloraxis_showscale=False
    )
    st.plotly_chart(fig_vel, use_container_width=True)

    # Giải thích công thức
    st.info("💡 **Viral Velocity** = (Views/Giờ × Engagement Rate) / log₁₀(Tuổi Video + 10). "
            "Video mới với tương tác cao sẽ có Velocity lớn nhất.")

# --- TAB 4: Timeline
with tab4:
    if 'scrape_date' in df.columns and df['scrape_date'].notna().any():
        timeline = df.groupby('scrape_date').agg(
            videos=('video_id', 'count'),
            avg_views=('views', 'mean'),
            avg_viral=('viral_probability', 'mean')
        ).reset_index()

        fig_timeline = go.Figure()
        fig_timeline.add_trace(go.Bar(
            x=timeline['scrape_date'], y=timeline['videos'],
            name='Số Video', marker_color='#667eea', opacity=0.7
        ))
        fig_timeline.add_trace(go.Scatter(
            x=timeline['scrape_date'], y=timeline['avg_viral'],
            name='Avg Viral %', yaxis='y2',
            line=dict(color='#e94560', width=3), mode='lines+markers'
        ))
        fig_timeline.update_layout(
            yaxis=dict(title='Số Video Thu Thập', gridcolor='#2d2d44'),
            yaxis2=dict(title='Avg Viral Probability %', overlaying='y', side='right', gridcolor='#2d2d44'),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0', legend=dict(orientation='h', y=-0.2),
            title="Lịch Sử Thu Thập & Chất Lượng Data Theo Thời Gian", height=400
        )
        st.plotly_chart(fig_timeline, use_container_width=True)
    else:
        st.info("📅 Chưa có dữ liệu ngày thu thập.")

# --- TAB 5: Phân Bổ Danh Mục
with tab5:
    if 'category' in df.columns:
        cat_counts = df['category'].value_counts().reset_index()
        cat_counts.columns = ['Danh Mục', 'Số Lượng']
        fig_cat = px.pie(cat_counts, values='Số Lượng', names='Danh Mục', hole=0.4, title="Phân Bổ Kênh Theo Danh Mục")
        fig_cat.update_traces(textposition='inside', textinfo='percent+label')
        fig_cat.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0')
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("🏷️ Chưa có dữ liệu phân loại danh mục.")


# ==========================================
# PHẦN 3.5: TỐC ĐỘ VIRAL THEO DANH MỤC GẦN ĐÂY
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>🔥 Tốc Độ Viral Theo Danh Mục — Gần Đây</h3></div>', unsafe_allow_html=True)
st.caption("So sánh tốc độ viral trung bình của từng danh mục theo các ngày thu thập gần nhất.")

if 'category' in df.columns and 'scrape_date' in df.columns and df['scrape_date'].notna().any():
    # Lấy tối đa 7 ngày gần nhất
    recent_dates = sorted(df['scrape_date'].dropna().unique(), reverse=True)[:7]
    df_recent = df[df['scrape_date'].isin(recent_dates)].copy()

    col_cv1, col_cv2 = st.columns([3, 2])

    with col_cv1:
        # Grouped Bar: Trung bình viral_velocity theo category × scrape_date
        cat_date_vel = df_recent.groupby(['category', 'scrape_date']).agg(
            avg_velocity=('viral_velocity', 'mean'),
            avg_viral=('viral_probability', 'mean'),
            count=('video_id', 'count')
        ).reset_index()

        fig_cv_bar = px.bar(
            cat_date_vel,
            x='scrape_date', y='avg_velocity', color='category',
            barmode='group',
            hover_data={'avg_viral': ':.1f', 'count': True},
            labels={
                'scrape_date': 'Ngày Thu Thập',
                'avg_velocity': 'Avg Viral Velocity',
                'category': 'Danh Mục',
                'avg_viral': 'Avg Viral %',
                'count': 'Số Video'
            },
            title="Tốc Độ Viral Trung Bình Theo Danh Mục & Ngày",
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig_cv_bar.update_layout(
            height=480,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0',
            legend=dict(orientation='h', y=-0.25),
            xaxis=dict(gridcolor='#2d2d44'),
            yaxis=dict(gridcolor='#2d2d44')
        )
        st.plotly_chart(fig_cv_bar, use_container_width=True)

    with col_cv2:
        # Heatmap: Category vs Date → Avg Viral Velocity
        heatmap_data = df_recent.pivot_table(
            index='category', columns='scrape_date',
            values='viral_velocity', aggfunc='mean'
        ).fillna(0)

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns.tolist(),
            y=heatmap_data.index.tolist(),
            colorscale=[[0, '#1a1a2e'], [0.35, '#16213e'], [0.6, '#e94560'], [1, '#ff6b6b']],
            hovertemplate='Danh mục: %{y}<br>Ngày: %{x}<br>Avg Velocity: %{z:.1f}<extra></extra>'
        ))
        fig_heatmap.update_layout(
            title="Heatmap: Viral Velocity × Danh Mục × Ngày",
            height=480,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0',
            xaxis=dict(title='Ngày', gridcolor='#2d2d44'),
            yaxis=dict(title='', gridcolor='#2d2d44', autorange='reversed')
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

    # Bảng xếp hạng danh mục nóng nhất hiện tại
    st.markdown("**🏆 Bảng Xếp Hạng Danh Mục Nóng Nhất (Gần Đây)**")
    cat_rank = df_recent.groupby('category').agg(
        avg_velocity=('viral_velocity', 'mean'),
        avg_viral=('viral_probability', 'mean'),
        avg_engagement=('engagement_rate', 'mean'),
        total_views=('views', 'sum'),
        video_count=('video_id', 'count')
    ).sort_values('avg_velocity', ascending=False).reset_index()

    cat_rank.columns = ['🏷️ Danh Mục', '🚀 Avg Velocity', '🔥 Avg Viral %',
                        '📈 Avg Engagement %', '👁️ Tổng Views', '📹 Số Video']

    st.dataframe(
        cat_rank,
        column_config={
            '🚀 Avg Velocity': st.column_config.NumberColumn(format='%.1f'),
            '🔥 Avg Viral %': st.column_config.ProgressColumn(format='%.1f%%', min_value=0, max_value=100),
            '📈 Avg Engagement %': st.column_config.NumberColumn(format='%.1f'),
            '👁️ Tổng Views': st.column_config.NumberColumn(format='%d'),
        },
        use_container_width=True, hide_index=True
    )
else:
    st.info("📅 Cần có cả danh mục và ngày thu thập để hiển thị phần này.")


# ==========================================
# PHẦN 4: PHÂN TÍCH CẢM XÚC & TỪ KHÓA
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>🧠 Phân Tích NLP: Cảm Xúc & Từ Khóa</h3></div>', unsafe_allow_html=True)

col_nlp1, col_nlp2 = st.columns([1, 2])

with col_nlp1:
    st.markdown("**Tỷ Trọng Cảm Xúc Bình Luận**")
    sentiment_data = df[df['video_sentiment'].notna() & (df['video_sentiment'] != "⚪ KHÔNG CÓ BÌNH LUẬN")]
    if len(sentiment_data) > 0:
        sentiment_counts = df['video_sentiment'].value_counts().reset_index()
        sentiment_counts.columns = ['Cảm Xúc', 'Số Lượng']

        fig_pie = px.pie(
            sentiment_counts,
            values='Số Lượng', names='Cảm Xúc', hole=0.45,
            color='Cảm Xúc',
            color_discrete_map={
                "🟢 TÍCH CỰC": "#00CC96",
                "🔴 TIÊU CỰC": "#EF553B",
                "🟡 TRUNG LẬP": "#FFA15A",
                "⚪ KHÔNG CÓ BÌNH LUẬN": "#4a5568"
            }
        )
        fig_pie.update_layout(
            showlegend=False, height=350,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0'
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

        # Positive Score distribution
        st.markdown("**Phân Bổ Điểm Tích Cực (Positive Score)**")
        fig_pos = px.histogram(
            df[df['positive_score'] > 0], x="positive_score", nbins=20,
            color_discrete_sequence=["#00CC96"],
            labels={"positive_score": "Positive Score (%)"}
        )
        fig_pos.update_layout(
            height=250, showlegend=False, margin=dict(t=10),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0'
        )
        st.plotly_chart(fig_pos, use_container_width=True)
    else:
        st.info("💡 Chưa có dữ liệu cảm xúc.")

with col_nlp2:
    st.markdown("**☁️ Từ Khóa Nổi Bật Trong Bình Luận**")

    # Gom tất cả keywords
    all_keywords = []
    for kw_str in df['top_keywords'].dropna():
        if isinstance(kw_str, str) and kw_str.strip():
            all_keywords.extend([k.strip() for k in kw_str.split(',') if k.strip()])

    if all_keywords:
        kw_counter = Counter(all_keywords)
        top_kws = kw_counter.most_common(30)

        # Hiển thị dưới dạng tag cloud giả lập
        tags_html = ""
        max_count = top_kws[0][1] if top_kws else 1
        for word, count in top_kws:
            # Scale font size dựa theo tần suất
            scale = 0.7 + (count / max_count) * 0.8
            tags_html += f'<span class="keyword-tag" style="font-size:{scale}rem;">{word.replace("_", " ")} ({count})</span> '

        st.markdown(tags_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Bar chart top keywords
        kw_df = pd.DataFrame(top_kws[:15], columns=['Từ Khóa', 'Tần Suất'])
        fig_kw = px.bar(
            kw_df, x='Tần Suất', y='Từ Khóa', orientation='h',
            color='Tần Suất', color_continuous_scale=["#667eea", "#764ba2"],
            labels={"Tần Suất": "Số Lần Xuất Hiện"}
        )
        fig_kw.update_layout(
            yaxis={'categoryorder': 'total ascending'},
            height=400, coloraxis_showscale=False,
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            font_color='#a0aec0', title="Top 15 Từ Khóa Nổi Bật"
        )
        st.plotly_chart(fig_kw, use_container_width=True)
    else:
        st.info("💡 Chưa có dữ liệu từ khóa.")


# ==========================================
# PHẦN 5: BÌNH LUẬN NỔI BẬT
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>💬 Bình Luận Nổi Bật — Top Video</h3></div>', unsafe_allow_html=True)
st.caption("Top 5 bình luận được thích nhiều nhất từ mỗi video hot.")

top_for_comments = df.sort_values('viral_probability', ascending=False).head(5)

for _, video in top_for_comments.iterrows():
    with st.expander(f"🎬 {video['Display_Name']} — Viral: {video['viral_probability']:.1f}% | {video['video_sentiment']}"):
        # Thông tin video
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("👁️ Views", f"{int(video['views']):,}")
        m2.metric("❤️ Likes", f"{int(video['likes']):,}")
        m3.metric("💬 Comments", f"{int(video['comments']):,}")
        m4.metric("🔄 Shares", f"{int(video['shares']):,}")
        m5.metric("🔖 Saves", f"{int(video['saves']):,}")

        # Metrics nhỏ
        st.markdown(
            f"⚡ View/Giờ: **{video['views_per_hour']:,.0f}** | "
            f"📈 Engagement: **{video['engagement_rate']:.1f}%** | "
            f"🚀 Velocity: **{video['viral_velocity']:,.1f}** | "
            f"😊 Positive: **{video['positive_score']:.0f}%** | "
            f"🔗 [Xem Video]({video['link']})"
        )

        # Top comments
        has_comments = False
        for i in range(1, 6):
            cmt = video.get(f'top{i}_cmt', '')
            cmt_likes = video.get(f'top{i}_likes', 0)
            if cmt and str(cmt).strip() and str(cmt) != 'nan':
                has_comments = True
                likes_str = f"❤️ {int(cmt_likes):,} likes" if cmt_likes and int(cmt_likes) > 0 else ""
                st.markdown(
                    f'<div class="comment-card">'
                    f'💬 {str(cmt)[:200]}'
                    f'<div class="comment-likes">{likes_str}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        if not has_comments:
            st.caption("Không có bình luận nào được thu thập.")

        # Keywords
        if video.get('top_keywords') and str(video['top_keywords']).strip() and str(video['top_keywords']) != 'nan':
            kw_tags = "".join(
                [f'<span class="keyword-tag">{k.strip().replace("_"," ")}</span>'
                 for k in str(video['top_keywords']).split(',') if k.strip()]
            )
            st.markdown(f"🏷️ **Từ khoá:** {kw_tags}", unsafe_allow_html=True)
            
        st.markdown(f"**Danh mục:** {video.get('category', 'Chưa phân loại')} | **Trạng thái MP4:** {video.get('has_video', '❌ Không')}")


# ==========================================
# PHẦN 6: SO SÁNH VIDEO
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>⚖️ So Sánh Đối Đầu: Top Viral vs Bottom</h3></div>', unsafe_allow_html=True)

col_compare1, col_compare2 = st.columns(2)

with col_compare1:
    st.markdown("**🔥 Top 5 — Video Tiềm Năng Nhất**")
    top5 = df.nlargest(5, 'viral_probability')
    for _, v in top5.iterrows():
        pct = v['viral_probability']
        bar_width = min(pct, 100)
        st.markdown(
            f"**{v['Display_Name'][:35]}**  \n"
            f"`{pct:.1f}%` viral | 👁️ {int(v['views']):,} | ❤️ {int(v['likes']):,}"
        )
        st.progress(bar_width / 100)

with col_compare2:
    st.markdown("**💤 Bottom 5 — Video Cần Cải Thiện**")
    bottom5 = df.nsmallest(5, 'viral_probability')
    for _, v in bottom5.iterrows():
        pct = v['viral_probability']
        bar_width = min(max(pct, 0), 100)
        st.markdown(
            f"**{v['Display_Name'][:35]}**  \n"
            f"`{pct:.1f}%` viral | 👁️ {int(v['views']):,} | ❤️ {int(v['likes']):,}"
        )
        st.progress(max(bar_width / 100, 0.01))


# ==========================================
# PHẦN 7: BẢNG DỮ LIỆU ĐẦY ĐỦ
# ==========================================
st.divider()
st.markdown('<div class="section-header"><h3>📋 Bảng Dữ Liệu Chiến Lược Đầy Đủ</h3></div>', unsafe_allow_html=True)

# Bộ lọc
col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    sentiment_filter = st.multiselect(
        "Lọc theo Cảm Xúc:",
        df['video_sentiment'].unique().tolist(),
        default=df['video_sentiment'].unique().tolist()
    )
with col_f2:
    category_filter = st.multiselect(
        "Lọc theo Danh Mục:",
        df['category'].unique().tolist(),
        default=df['category'].unique().tolist()
    )
with col_f3:
    min_viral = st.slider("Viral Probability tối thiểu:", 0.0, 100.0, 0.0, 1.0)
with col_f4:
    sort_col = st.selectbox("Sắp xếp theo:", [
        "viral_probability", "views", "likes", "engagement_rate",
        "viral_velocity", "views_per_hour", "positive_score"
    ])

df_filtered = df[
    (df['video_sentiment'].isin(sentiment_filter)) &
    (df['category'].isin(category_filter)) &
    (df['viral_probability'] >= min_viral)
].sort_values(by=sort_col, ascending=False)

st.caption(f"Hiển thị {len(df_filtered)} / {len(df)} video")

display_cols = [
    'link', 'Display_Name', 'category', 'viral_probability', 'video_sentiment',
    'views', 'likes', 'comments', 'shares', 'saves',
    'views_per_hour', 'engagement_rate', 'viral_velocity', 'positive_score',
    'top_keywords', 'has_video', 'scrape_date'
]
valid_cols = [col for col in display_cols if col in df_filtered.columns]

st.dataframe(
    df_filtered[valid_cols],
    column_config={
        "viral_probability": st.column_config.ProgressColumn(
            "🔥 Viral %", format="%.1f%%", min_value=0, max_value=100,
        ),
        "positive_score": st.column_config.ProgressColumn(
            "😊 Positive", format="%.0f%%", min_value=0, max_value=100,
        ),
        "link": st.column_config.LinkColumn("🔗 Link"),
        "Display_Name": "📹 Video",
        "category": "🏷️ Danh Mục",
        "has_video": "🎬 Đã Tải MP4",
        "video_sentiment": "💭 Cảm Xúc",
        "views": st.column_config.NumberColumn("👁️ Views", format="%d"),
        "likes": st.column_config.NumberColumn("❤️ Likes", format="%d"),
        "comments": st.column_config.NumberColumn("💬 Comments", format="%d"),
        "shares": st.column_config.NumberColumn("🔄 Shares", format="%d"),
        "saves": st.column_config.NumberColumn("🔖 Saves", format="%d"),
        "views_per_hour": st.column_config.NumberColumn("⚡ View/h", format="%.0f"),
        "engagement_rate": st.column_config.NumberColumn("📈 Engage %", format="%.1f"),
        "viral_velocity": st.column_config.NumberColumn("🚀 Velocity", format="%.1f"),
        "top_keywords": "🏷️ Keywords",
        "scrape_date": "📅 Ngày Cào",
    },
    use_container_width=True,
    hide_index=True,
    height=500
)


# ==========================================
# FOOTER
# ==========================================
st.divider()
st.markdown(
    '<p style="text-align:center; color:#4a5568; font-size:0.8rem;">'
    '🎯 TrendSense Radar — AI-Powered Viral Prediction System<br>'
    'Pipeline: Selenium Scraper → SQLite → BERT NLP → RandomForest → Streamlit'
    '</p>',
    unsafe_allow_html=True
)