import streamlit as st
import pandas as pd
import numpy as np
from database.connection import get_engine
from dashboard.components.charts import candlestick_chart, fear_greed_gauge, sentiment_time_series
from signals.fear_greed_index import FearGreedIndex
from config.coins import TRACKED_COINS


def render():
    st.markdown("## 📊 Live Dashboard")

    engine = get_engine()

    # Top metrics row
    cols = st.columns(len(TRACKED_COINS))
    for i, (symbol, info) in enumerate(TRACKED_COINS.items()):
        with cols[i]:
            try:
                price_df = pd.read_sql(f"""
                    SELECT close, timestamp FROM price_data
                    WHERE coin = '{symbol}' AND interval = '15m'
                    ORDER BY timestamp DESC LIMIT 2
                """, engine)

                if not price_df.empty:
                    current = price_df.iloc[0]["close"]
                    prev = price_df.iloc[1]["close"] if len(price_df) > 1 else current
                    change = (current - prev) / prev * 100

                    sent_df = pd.read_sql(f"""
                        SELECT avg_sentiment FROM sentiment_aggregated
                        WHERE coin = '{symbol}' AND window_size = '4h'
                        ORDER BY window_start DESC LIMIT 1
                    """, engine)
                    sent = float(sent_df.iloc[0]["avg_sentiment"]) if not sent_df.empty else 0.5

                    color = info["color"]
                    arrow = "▲" if change >= 0 else "▼"
                    change_color = "#00D4A8" if change >= 0 else "#FF4C4C"

                    st.markdown(f"""
                    <div class="metric-card">
                        <div style="color:{color};font-weight:700;font-size:1rem;margin-bottom:4px;">{symbol}</div>
                        <div style="font-family:'Space Mono',monospace;font-size:1.3rem;font-weight:700;">${current:,.2f}</div>
                        <div style="color:{change_color};font-size:0.85rem;margin-top:4px;">{arrow} {abs(change):.2f}%</div>
                        <div style="color:#8B95A1;font-size:0.7rem;margin-top:6px;">
                            Sent: {sent:.2f} {'😊' if sent > 0.6 else '😰' if sent < 0.4 else '😐'}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info(f"No price data for {symbol}")
            except Exception as e:
                st.error(f"{symbol}: {e}")

    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        selected_coin = st.selectbox("Select Coin", list(TRACKED_COINS.keys()), key="ld_coin")
        try:
            price_df = pd.read_sql(f"""
                SELECT timestamp, open, high, low, close, volume FROM price_data
                WHERE coin = '{selected_coin}' AND interval = '15m'
                AND timestamp > NOW() - INTERVAL '48 hours'
                ORDER BY timestamp ASC
            """, engine)
            if not price_df.empty:
                price_df.set_index("timestamp", inplace=True)
                st.plotly_chart(candlestick_chart(price_df, f"{selected_coin} / USDT — 15m", selected_coin), use_container_width=True)
        except Exception as e:
            st.error(f"Chart error: {e}")

    with col2:
        st.markdown("### ⚡ Fear & Greed")
        try:
            fg = FearGreedIndex().calculate()
            st.plotly_chart(fear_greed_gauge(fg["index_value"]), use_container_width=True)
            label_colors = {
                "Extreme Fear": "#FF4C4C", "Fear": "#FF7B54",
                "Neutral": "#FFB830", "Greed": "#00D4A8", "Extreme Greed": "#00FF9C"
            }
            color = label_colors.get(fg["label"], "#FFB830")
            st.markdown(f"""
            <div style="text-align:center;padding:8px;background:#1A1F2E;border-radius:8px;border:1px solid #2D3445;">
                <span style="color:{color};font-weight:700;font-family:'Space Mono',monospace;font-size:1.1rem;">
                    {fg['label'].upper()}
                </span>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"F&G error: {e}")

        st.markdown("### 📡 Latest Signals")
        try:
            signals_df = pd.read_sql("""
                SELECT coin, signal_type, confidence, generated_at
                FROM signals ORDER BY generated_at DESC LIMIT 10
            """, engine)
            for _, s in signals_df.iterrows():
                color = {"BUY": "#00D4A8", "STRONG_BUY": "#00FF9C",
                         "SELL": "#FF4C4C", "STRONG_SELL": "#FF0000", "HOLD": "#4C9BE8"}.get(s["signal_type"], "#8B95A1")
                st.markdown(f"""
                <div style="padding:6px 10px;margin:3px 0;background:#1A1F2E;border-radius:6px;border-left:3px solid {color};">
                    <span style="color:{color};font-weight:600;font-family:'Space Mono',monospace;font-size:0.8rem;">
                        {s['coin']} · {s['signal_type']}
                    </span>
                    <span style="color:#8B95A1;font-size:0.7rem;margin-left:8px;">{s['confidence']:.0%}</span>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Signals error: {e}")

    st.markdown("---")
    st.markdown("### 💬 Market Sentiment Overview")
    sent_cols = st.columns(len(TRACKED_COINS))
    for i, (symbol, _) in enumerate(TRACKED_COINS.items()):
        with sent_cols[i]:
            try:
                sent_df = pd.read_sql(f"""
                    SELECT window_start, avg_sentiment FROM sentiment_aggregated
                    WHERE coin = '{symbol}' AND window_size = '1h'
                    AND window_start > NOW() - INTERVAL '48 hours'
                    ORDER BY window_start ASC
                """, engine)
                if not sent_df.empty:
                    st.plotly_chart(sentiment_time_series(sent_df, symbol), use_container_width=True)
            except Exception:
                st.info(f"No sentiment data for {symbol}")
