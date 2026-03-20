# 🚀 TrendSense - Phân tích Trend TikTok bằng AI

## Cấu trúc dự án

```
├── data/                   # Dữ liệu thô và đã xử lý
├── src/                    # Source code chính
│   ├── scraper/           # Cào data TikTok (Apify)
│   ├── ai_core/           # AI phân tích (NLP, Keywords)
│   └── dashboard/         # Streamlit Dashboard
├── config/                # Cấu hình hệ thống
├── .env                   # API Keys (KHÔNG commit)
├── requirements.txt       # Dependencies
└── README.md
```

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # Điền API keys của bạn
streamlit run src/dashboard/app.py
```

## Các phân hệ

1. **Scraper**: `python src/scraper/apify_bot.py`
2. **AI Core**: Sentiment analysis + Keywords extraction
3. **Dashboard**: Web realtime tại http://localhost:8501
