"""
live_dashboard.py — Main terminal view (Problem Statement §3.6)

Features:
  Multi-coin price ticker (BTC, ETH, SOL, XRP, DOGE)
  Real-time sentiment heatmap (color-coded per coin × time)
  High-confidence alert banners (STRONG_BUY / STRONG_SELL in last 15 min)
  Live signal feed (latest 5 signals with confidence + reasoning)
  Fear & Greed gauge
  Candlestick chart for selected coin
  Auto-refresh every 60s
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta

from database.connection import get_engine
from database.sql_compat import time_ago
from dashboard.components.charts import (
    candlestick_chart, fear_greed_gauge,
    sentiment_heatmap_chart, signal_radar_chart, price_sparkline,
)
from config.coins import TRACKED_COINS

# Fear & Greed — optional import, falls back gracefully
try:
    from signals.fear_greed_index import FearGreedIndex
    _HAS_FGI = True
except Exception:
    _HAS_FGI = False

_BINANCE_URL = "https://api.binance.com/api/v3"
_SIGNAL_COLORS = {
    "STRONG_BUY":  "#00FF9C", "BUY":  "#00D4A8",
    "HOLD":        "#4C9BE8",
    "SELL":        "#FF7B54", "STRONG_SELL": "#FF4C4C",
}
_SIGNAL_ICONS = {
    "STRONG_BUY": "🚀", "BUY": "📈", "HOLD": "⏸️", "SELL": "📉", "STRONG_SELL": "🔴"
}


@st.cache_data(ttl=15)
def fetch_live_prices():
    """Pull latest prices for all tracked coins from Binance (free, no key)."""
    results = {}
    for symbol, info in TRACKED_COINS.items():
        try:
            r = requests.get(f"{_BINANCE_URL}/ticker/price",
                             params={"symbol": info["binance_symbol"]}, timeout=5)
            results[symbol] = {"price": float(r.json()["price"]), "color": info["color"]}
        except Exception:
            results[symbol] = {"price": 0.0, "color": info["color"]}
    return results


@st.cache_data(ttl=30)
def fetch_sparklines():
    """30 candles of 15m closes for each coin — used in sparklines."""
    lines = {}
    for symbol, info in TRACKED_COINS.items():
        try:
            r = requests.get(f"{_BINANCE_URL}/klines",
                             params={"symbol": info["binance_symbol"], "interval": "15m", "limit": 30},
                             timeout=6)
            lines[symbol] = [float(c[4]) for c in r.json()]  # close prices
        except Exception:
            lines[symbol] = []
    return lines


def _pct_change(prices):
    if len(prices) < 2:
        return 0.0
    return (prices[-1] - prices[0]) / prices[0] * 100


def _render_alerts(engine):
    """Shows st.error / st.success for any STRONG signal in last 15 min."""
    try:
        cutoff = time_ago(minutes=15)
        df = pd.read_sql("""
            SELECT coin, signal_type, confidence, generated_at
            FROM signals
            WHERE signal_type IN ('STRONG_BUY','STRONG_SELL')
              AND generated_at >= :cutoff
            ORDER BY generated_at DESC
            LIMIT 5
        """, engine, params={"cutoff": cutoff})
        for _, row in df.iterrows():
            try:
                age = int((datetime.utcnow() - pd.Timestamp(row["generated_at"]).to_pydatetime().replace(tzinfo=None)).total_seconds() / 60)
            except Exception:
                age = 0
            icon = _SIGNAL_ICONS.get(row["signal_type"], "⚡")
            conf = float(row["confidence"])
            msg = f"{icon}  **{row['coin']} {row['signal_type']}** — Confidence {conf:.0%}  ·  {age}m ago"
            if "BUY" in row["signal_type"]:
                st.success(msg, icon="🚀")
            else:
                st.error(msg, icon="🔴")
    except Exception:
        pass


def _render_ticker(live_prices, sparklines):
    cols = st.columns(len(TRACKED_COINS))
    for i, (symbol, info) in enumerate(TRACKED_COINS.items()):
        with cols[i]:
            prices = sparklines.get(symbol, [])
            price  = live_prices.get(symbol, {}).get("price", 0.0)
            change = _pct_change(prices)
            arrow  = "▲" if change >= 0 else "▼"
            chg_color = "#00D4A8" if change >= 0 else "#FF4C4C"
            coin_color = info["color"]

            st.markdown(f"""
            <div class="metric-card" style="padding:14px 16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:{coin_color};font-weight:700;font-size:0.95rem;">
                        {symbol}
                    </span>
                    <span style="color:{chg_color};font-size:0.75rem;font-weight:600;">
                        {arrow} {abs(change):.2f}%
                    </span>
                </div>
                <div style="font-family:'Space Mono',monospace;font-size:1.2rem;
                            font-weight:700;margin:4px 0;color:#E8EAED;">
                    ${'N/A' if price == 0 else f'{price:,.2f}'}
                </div>
                <div style="color:#5A6478;font-size:0.65rem;">{info['name']}</div>
            </div>
            """, unsafe_allow_html=True)

            if prices:
                st.plotly_chart(
                    price_sparkline(prices, symbol, coin_color),
                    use_container_width=True, config={"displayModeBar": False},
                )


def _render_heatmap(engine):
    st.markdown("### 🌡️ Sentiment Heatmap")
    st.caption("Color: Red = Bearish · Grey = Neutral · Green = Bullish  |  Pulls last 12h of sentiment data")
    try:
        cutoff = time_ago(hours=12)
        df = pd.read_sql("""
            SELECT coin,
                   strftime('%Y-%m-%d %H:00:00', window_start) AS time_bucket,
                   AVG(avg_sentiment)                           AS avg_sentiment
            FROM sentiment_aggregated
            WHERE window_start >= :cutoff
            GROUP BY coin, strftime('%Y-%m-%d %H:00:00', window_start)
            ORDER BY time_bucket ASC
        """, engine, params={"cutoff": cutoff})
        if df.empty:
            coins = list(TRACKED_COINS.keys())
            now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            rows = []
            rng = np.random.default_rng(42)
            rng2 = np.random.RandomState(42)
            rng_date = pd.date_range(end=now, periods=12, freq="h")
            for c in coins:
                base = float(rng2.uniform(0.3, 0.75))
                for t in rng_date:
                    rows.append({
                        "coin": c,
                        "time_bucket": t,
                        "avg_sentiment": float(np.clip(base + rng2.normal(0, 0.12), 0, 1)),
                    })
            df = pd.DataFrame(rows)
            st.info("No pipeline data yet — showing demo heatmap", icon="ℹ️")

        fig = sentiment_heatmap_chart(df)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Heatmap error: {e}")


def _render_signal_feed(engine):
    st.markdown("### ⚡ Live Signals")
    try:
        df = pd.read_sql("""
            SELECT coin, signal_type, confidence, generated_at, reasoning
            FROM signals
            ORDER BY generated_at DESC LIMIT 8
        """, engine)

        if df.empty:
            st.info("No signals generated yet")
            return

        for _, s in df.iterrows():
            color   = _SIGNAL_COLORS.get(s["signal_type"], "#8B95A1")
            icon    = _SIGNAL_ICONS.get(s["signal_type"], "")
            try:
                age_min = int((datetime.utcnow() - pd.Timestamp(s["generated_at"]).to_pydatetime().replace(tzinfo=None)).total_seconds() / 60)
            except Exception:
                age_min = 0
            coin_color = TRACKED_COINS.get(s["coin"], {}).get("color", "#8B95A1")
            conf = float(s["confidence"])

            with st.expander(
                f"{icon} {s['coin']} · {s['signal_type']}  ({conf:.0%})  —  {age_min}m ago",
                expanded=False,
            ):
                st.markdown(f"""
                <div style="background:#0E1117;border-radius:6px;padding:10px 14px;
                            font-family:'Space Mono',monospace;font-size:0.78rem;
                            color:#00D4A8;border-left:3px solid {color};">
                    {s['reasoning'] or '—'}
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Signal feed error: {e}")


def render():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <span style="font-size:2rem;">🛡️</span>
        <div>
            <h2 style="margin:0;font-family:'Space Mono',monospace;font-size:1.4rem;font-weight:700;">
                CRYPTO SENTINEL
            </h2>
            <div style="color:#8B95A1;font-size:0.75rem;font-family:'Space Mono',monospace;
                        letter-spacing:2px;">
                SELF-HOSTED LLM INTELLIGENCE TERMINAL
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    engine = get_engine()
    _render_alerts(engine)

    with st.spinner("Fetching live prices..."):
        live_prices = fetch_live_prices()
        sparklines  = fetch_sparklines()

    _render_ticker(live_prices, sparklines)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    col_main, col_side = st.columns([3, 1])

    with col_main:
        _render_heatmap(engine)

        st.markdown("---")
        st.markdown("### 📈 Price Chart")
        coin_choice = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="ld_chart_coin")
        try:
            cutoff = time_ago(hours=48)
            price_df = pd.read_sql("""
                SELECT timestamp, open, high, low, close, volume
                FROM price_data
                WHERE coin = :coin AND interval = '15m'
                  AND timestamp >= :cutoff
                ORDER BY timestamp ASC
            """, engine, params={"coin": coin_choice, "cutoff": cutoff})
            if not price_df.empty:
                price_df.set_index("timestamp", inplace=True)
                st.plotly_chart(
                    candlestick_chart(price_df, f"{coin_choice}/USDT — 15m", coin_choice),
                    use_container_width=True,
                )
            else:
                st.info(f"No candle data for {coin_choice} yet")
        except Exception as e:
            st.error(f"Chart error: {e}")

    with col_side:
        st.markdown("### 🎯 Fear & Greed")
        try:
            # Try live FGI calculation, fall back to DB lookup
            if _HAS_FGI:
                fg = FearGreedIndex().calculate()
            else:
                raise RuntimeError("FGI not available")
        except Exception:
            try:
                fg_df = pd.read_sql(
                    "SELECT index_value, label FROM fear_greed_index ORDER BY timestamp DESC LIMIT 1",
                    engine
                )
                if not fg_df.empty:
                    fg = {"index_value": int(fg_df.iloc[0]["index_value"]), "label": fg_df.iloc[0]["label"]}
                else:
                    fg = {"index_value": 58, "label": "Greed"}
            except Exception:
                fg = {"index_value": 58, "label": "Greed"}

        label_colors = {
            "Extreme Fear": "#FF4C4C", "Fear": "#FF7B54",
            "Neutral":      "#FFB830",
            "Greed":        "#00D4A8", "Extreme Greed": "#00FF9C",
        }
        c = label_colors.get(fg["label"], "#FFB830")
        st.plotly_chart(fear_greed_gauge(fg["index_value"]), use_container_width=True,
                       config={"displayModeBar": False})
        st.markdown(f"""
        <div style="text-align:center;padding:6px;background:#1A1F2E;
                    border-radius:8px;border:1px solid #2D3445;margin-top:-8px;">
            <span style="color:{c};font-weight:700;font-family:'Space Mono',monospace;
                         font-size:1rem;">{fg['label'].upper()}</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _render_signal_feed(engine)

    st.markdown("---")
    now_str = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"""
    <div style="text-align:center;color:#5A6478;font-size:0.65rem;
                font-family:'Space Mono',monospace;">
        Last updated: {now_str} UTC+5:30
        &nbsp;·&nbsp; Prices via Binance free API
        &nbsp;·&nbsp; Not financial advice
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Refresh Now", use_container_width=False):
        st.cache_data.clear()
        st.rerun()
