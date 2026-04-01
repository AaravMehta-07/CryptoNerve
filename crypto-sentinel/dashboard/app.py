"""
app.py — Crypto Sentinel · Streamlit Entry Point
Premium dark glassmorphic design for NMIMS INNOVATHON 2026
"""
import streamlit as st

st.set_page_config(
    page_title="Crypto Sentinel — LLM Market Intelligence Terminal",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS — Premium Glassmorphic Dark Theme
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap');

/* ── Reset & base ── */
:root {
    --bg-primary:    #080C14;
    --bg-secondary:  #0F1623;
    --bg-card:       #111827;
    --bg-card-hover: #151E2D;
    --accent-orange: #FF6B35;
    --accent-green:  #00D4A8;
    --accent-neon:   #00FF9C;
    --accent-red:    #FF4C4C;
    --accent-blue:   #4C9BE8;
    --accent-yellow: #FFB830;
    --accent-purple: #8B5CF6;
    --text-primary:  #E8EAED;
    --text-secondary:#A0AEC0;
    --text-muted:    #5A6478;
    --border:        #1E2A3F;
    --border-glow:   rgba(0,212,168,0.3);
    --shadow-card:   0 4px 24px rgba(0,0,0,0.4);
    --shadow-glow:   0 0 20px rgba(0,212,168,0.15);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* Animated gradient background */
.main {
    background:
        radial-gradient(ellipse at 20% 20%, rgba(0,212,168,0.03) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 80%, rgba(76,155,232,0.03) 0%, transparent 50%),
        var(--bg-primary) !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-green); }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #060A11 0%, #0A1020 100%) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.5) !important;
}
[data-testid="stSidebar"] > div { padding-top: 0 !important; }

/* ── Sidebar nav radio ── */
[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 14px !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    border: 1px solid transparent !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(0,212,168,0.06) !important;
    color: var(--accent-green) !important;
    border-color: rgba(0,212,168,0.15) !important;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio [data-checked="true"] + label {
    background: rgba(0,212,168,0.1) !important;
    color: var(--accent-green) !important;
    border-color: rgba(0,212,168,0.3) !important;
    font-weight: 600 !important;
}

/* ── Cards ── */
.metric-card {
    background: linear-gradient(135deg, var(--bg-card) 0%, rgba(15,22,35,0.95) 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px 20px;
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,212,168,0.4), transparent);
}
.metric-card:hover {
    border-color: rgba(0,212,168,0.25);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,212,168,0.1);
    transform: translateY(-1px);
}

/* ── Signal badges ── */
.signal-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.5px;
}
.signal-STRONG_BUY  { background: rgba(0,255,156,0.12); color: #00FF9C; border: 1px solid rgba(0,255,156,0.3); }
.signal-BUY         { background: rgba(0,212,168,0.12); color: #00D4A8; border: 1px solid rgba(0,212,168,0.3); }
.signal-HOLD        { background: rgba(76,155,232,0.12); color: #4C9BE8; border: 1px solid rgba(76,155,232,0.3); }
.signal-SELL        { background: rgba(255,123,84,0.12); color: #FF7B54; border: 1px solid rgba(255,123,84,0.3); }
.signal-STRONG_SELL { background: rgba(255,76,76,0.12); color: #FF4C4C; border: 1px solid rgba(255,76,76,0.3); }

/* ── Terminal text ── */
.terminal-text {
    font-family: 'Space Mono', monospace !important;
    color: var(--accent-neon) !important;
    font-size: 0.82rem;
}

/* ── Streamlit metric ── */
div[data-testid="stMetricValue"] {
    font-family: 'Space Mono', monospace !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}
div[data-testid="stMetricDelta"] svg { display: none; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, var(--accent-orange) 0%, #E84C00 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    padding: 0.55rem 1.6rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 12px rgba(255,107,53,0.3) !important;
    letter-spacing: 0.3px !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(255,107,53,0.45) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
    border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text-muted) !important;
    font-weight: 500 !important;
    font-size: 0.83rem !important;
    padding: 6px 16px !important;
    transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(0,212,168,0.12) !important;
    color: var(--accent-green) !important;
    font-weight: 600 !important;
}

/* ── Selectbox / multiselect ── */
[data-testid="stSelectbox"] div[data-baseweb],
.stMultiSelect div[data-baseweb] {
    background: var(--bg-card) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
}

/* ── DataFrames ── */
.stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
.stDataFrame thead { background: var(--bg-card) !important; }
.stDataFrame tbody tr:hover { background: rgba(0,212,168,0.04) !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    margin-bottom: 6px !important;
    transition: border-color 0.2s !important;
}
[data-testid="stExpander"]:hover { border-color: rgba(0,212,168,0.2) !important; }
[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    font-family: 'Space Mono', monospace !important;
}

/* ── Alerts — success/error ── */
[data-testid="stNotification"] {
    border-radius: 10px !important;
    border-width: 1px !important;
}

/* ── Divider ── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, var(--border), transparent) !important;
    margin: 16px 0 !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent-green) !important; }

/* ── Info box ── */
[data-testid="stInfoBox"] {
    background: rgba(76,155,232,0.08) !important;
    border-color: rgba(76,155,232,0.25) !important;
    border-radius: 10px !important;
}

/* ── Progress / slider track ── */
[role="progressbar"] > div { background: var(--accent-green) !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--accent-green) !important; }

/* ── Plotly charts ── */
.js-plotly-plot { border-radius: 10px !important; overflow: hidden !important; }

/* ── Caption/small text ── */
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
    font-size: 0.75rem !important;
}

/* ── Toast ── */
[data-testid="toastContainer"] [data-testid] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
}

/* ── Hide Streamlit branding ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ── Animated glow pulse for STRONG signals ── */
@keyframes glowPulse {
    0%   { box-shadow: 0 0 4px rgba(0,255,156,0.3); }
    50%  { box-shadow: 0 0 16px rgba(0,255,156,0.6), 0 0 30px rgba(0,255,156,0.2); }
    100% { box-shadow: 0 0 4px rgba(0,255,156,0.3); }
}
.glow-green { animation: glowPulse 2.5s ease-in-out infinite; }

@keyframes glowRed {
    0%   { box-shadow: 0 0 4px rgba(255,76,76,0.3); }
    50%  { box-shadow: 0 0 16px rgba(255,76,76,0.6), 0 0 30px rgba(255,76,76,0.2); }
    100% { box-shadow: 0 0 4px rgba(255,76,76,0.3); }
}
.glow-red { animation: glowRed 2.5s ease-in-out infinite; }

/* ── Confidence bar ── */
.conf-bar-wrap {
    background: #0E1117;
    border-radius: 4px;
    height: 5px;
    width: 100%;
    overflow: hidden;
    margin: 5px 0 2px;
}
.conf-bar-fill {
    height: 5px;
    border-radius: 4px;
    transition: width 0.8s cubic-bezier(0.4,0,0.2,1);
}

/* ── Page title style ── */
.page-title {
    font-family: 'Space Mono', monospace;
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}
.page-subtitle {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-bottom: 18px;
    letter-spacing: 0.3px;
}

/* ── Top gradient rule ── */
.gradient-rule {
    height: 2px;
    background: linear-gradient(90deg,
        rgba(0,212,168,0), rgba(0,212,168,0.6) 30%,
        rgba(76,155,232,0.6) 70%, rgba(76,155,232,0));
    border-radius: 2px;
    margin: 12px 0 20px;
}
</style>
""", unsafe_allow_html=True)

# Header bar
from dashboard.components.header import render_header
render_header()

# Navigation
pages = {
    "📊 Live Dashboard":        "dashboard.pages.live_dashboard",
    "📈 Price & Technicals":    "dashboard.pages.price_technicals",
    "💬 Sentiment Analysis":    "dashboard.pages.sentiment_analysis",
    "🐋 On-Chain Intelligence": "dashboard.pages.onchain_intelligence",
    "🤖 AI Predictions":        "dashboard.pages.ai_predictions",
    "⚡ Signals & Alerts":      "dashboard.pages.signals_alerts",
    "⏳ Backtesting":           "dashboard.pages.backtesting_page",
    "📝 AI Reports":            "dashboard.pages.ai_reports",
    "🔍 Explainability":        "dashboard.pages.explainability_page",
    "📊 Model Performance":     "dashboard.pages.model_performance",
}

from dashboard.components.sidebar import render_sidebar
selected = render_sidebar(list(pages.keys()))

# Gradient divider under header
st.markdown('<div class="gradient-rule"></div>', unsafe_allow_html=True)

# Dynamic page load
import importlib
try:
    page_module = pages[selected]
    mod = importlib.import_module(page_module)
    mod.render()
except Exception as e:
    st.error(f"⚠️ Page load error: {e}")
    import traceback
    with st.expander("Traceback"):
        st.code(traceback.format_exc())
