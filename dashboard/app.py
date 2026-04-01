import streamlit as st
from dashboard.components.sidebar import render_sidebar
from dashboard.components.header import render_header

st.set_page_config(
    page_title="Crypto Sentinel — LLM Market Intelligence Terminal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');

:root {
    --bg-primary: #0E1117;
    --bg-secondary: #1A1F2E;
    --accent-orange: #FF6B35;
    --accent-green: #00D4A8;
    --accent-red: #FF4C4C;
    --accent-blue: #4C9BE8;
    --text-primary: #E8EAED;
    --text-muted: #8B95A1;
    --border: #2D3445;
    --card-bg: #1A1F2E;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

.main { background-color: var(--bg-primary); }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1025 0%, #111927 100%) !important;
    border-right: 1px solid var(--border);
}

.metric-card {
    background: linear-gradient(135deg, #1A1F2E 0%, #141B2D 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s ease;
}
.metric-card:hover { border-color: var(--accent-orange); }

.signal-BUY, .signal-STRONG_BUY { color: var(--accent-green); }
.signal-SELL, .signal-STRONG_SELL { color: var(--accent-red); }
.signal-HOLD { color: var(--accent-blue); }

.terminal-text {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: var(--accent-green);
}

div[data-testid="stMetricValue"] {
    font-family: 'Space Mono', monospace;
    font-size: 1.5rem;
    font-weight: 700;
}

.stButton > button {
    background: linear-gradient(135deg, var(--accent-orange), #FF3D00) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(255, 107, 53, 0.4) !important;
}

[data-testid="stSelectbox"], [data-testid="stMultiSelect"] div {
    background: var(--bg-secondary) !important;
    border-color: var(--border) !important;
}

.stTabs [data-baseweb="tab-list"] { background: var(--bg-secondary); border-radius: 8px; }
.stTabs [data-baseweb="tab"] { color: var(--text-muted); font-weight: 500; }
.stTabs [aria-selected="true"] { color: var(--accent-orange) !important; }

div[data-baseweb="notification"] { background: var(--bg-secondary) !important; }
</style>
""", unsafe_allow_html=True)

# Navigation
render_header()

pages = {
    "📊 Live Dashboard": "dashboard.pages.live_dashboard",
    "📈 Price & Technicals": "dashboard.pages.price_technicals",
    "💬 Sentiment Analysis": "dashboard.pages.sentiment_analysis",
    "🐋 On-Chain Intelligence": "dashboard.pages.onchain_intelligence",
    "🤖 AI Predictions": "dashboard.pages.ai_predictions",
    "⚡ Signals & Alerts": "dashboard.pages.signals_alerts",
    "⏳ Backtesting": "dashboard.pages.backtesting_page",
    "📝 AI Reports": "dashboard.pages.ai_reports",
    "🔍 Explainability": "dashboard.pages.explainability_page",
    "📊 Model Performance": "dashboard.pages.model_performance",
}

selected = render_sidebar(list(pages.keys()))

# Dynamic page load
import importlib
page_module = pages[selected]
mod = importlib.import_module(page_module)
mod.render()
