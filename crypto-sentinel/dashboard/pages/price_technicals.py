import streamlit as st
import pandas as pd
from database.connection import get_engine
from database.sql_compat import time_ago
from dashboard.components.charts import candlestick_chart, _apply_theme
from config.coins import TRACKED_COINS
import plotly.graph_objects as go


def render():
    st.markdown("## 📈 Price & Technical Analysis")

    engine = get_engine()
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="pt_coin")
    with col2:
        interval = st.selectbox("Interval", ["15m", "1h", "4h"], key="pt_interval")
    with col3:
        lookback = st.selectbox("Lookback", ["24h", "48h", "7d", "30d"], key="pt_lookback")

    lookback_map = {"24h": 24, "48h": 48, "7d": 168, "30d": 720}
    hours = lookback_map.get(lookback, 48)
    cutoff = time_ago(hours=hours)

    try:
        price_df = pd.read_sql("""
            SELECT timestamp, open, high, low, close, volume FROM price_data
            WHERE coin = :coin AND interval = :interval
            AND timestamp >= :cutoff
            ORDER BY timestamp ASC
        """, engine, params={"coin": coin, "interval": interval, "cutoff": cutoff})

        # Technical indicators use 1h data regardless of selected interval
        ind_df = pd.read_sql("""
            SELECT timestamp, rsi, macd, macd_signal, macd_histogram,
                   bb_upper, bb_middle, bb_lower, atr
            FROM technical_indicators
            WHERE coin = :coin AND interval = '1h'
            AND timestamp >= :cutoff
            ORDER BY timestamp ASC
        """, engine, params={"coin": coin, "cutoff": cutoff})

        if not price_df.empty:
            price_df.set_index("timestamp", inplace=True)

            if not ind_df.empty:
                ind_df.set_index("timestamp", inplace=True)
                price_df = price_df.join(ind_df, how="left")

            fig = candlestick_chart(price_df, f"{coin}/USDT — {interval}", coin)
            if "bb_upper" in price_df.columns and price_df["bb_upper"].notna().any():
                fig.add_trace(go.Scatter(x=price_df.index, y=price_df["bb_upper"],
                    name="BB Upper", line=dict(color="#4C9BE8", dash="dot", width=1)))
                fig.add_trace(go.Scatter(x=price_df.index, y=price_df["bb_lower"],
                    name="BB Lower", line=dict(color="#4C9BE8", dash="dot", width=1),
                    fill="tonexty", fillcolor="rgba(76,155,232,0.05)"))

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No price data for {coin}/{interval}. Run pipeline to collect data.")

        if not ind_df.empty:
            col_rsi, col_macd = st.columns(2)
            with col_rsi:
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=ind_df.index, y=ind_df["rsi"],
                    mode="lines", name="RSI", line=dict(color="#FF6B35", width=2)))
                fig2.add_hline(y=70, line_dash="dash", line_color="#FF4C4C", opacity=0.6)
                fig2.add_hline(y=30, line_dash="dash", line_color="#00D4A8", opacity=0.6)
                fig2.add_hrect(y0=70, y1=100, fillcolor="rgba(255,76,76,0.05)")
                fig2.add_hrect(y0=0, y1=30, fillcolor="rgba(0,212,168,0.05)")
                _apply_theme(fig2, "RSI (14)")
                fig2.update_yaxes(range=[0, 100])
                st.plotly_chart(fig2, use_container_width=True)

            with col_macd:
                fig3 = go.Figure()
                fig3.add_trace(go.Scatter(x=ind_df.index, y=ind_df["macd"],
                    mode="lines", name="MACD", line=dict(color="#FF6B35", width=2)))
                fig3.add_trace(go.Scatter(x=ind_df.index, y=ind_df["macd_signal"],
                    mode="lines", name="Signal", line=dict(color="#4C9BE8", width=1)))
                hist_colors = ["#00D4A8" if v >= 0 else "#FF4C4C"
                               for v in ind_df["macd_histogram"].fillna(0)]
                fig3.add_trace(go.Bar(x=ind_df.index, y=ind_df["macd_histogram"],
                    name="Histogram", marker_color=hist_colors))
                _apply_theme(fig3, "MACD")
                st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### 📐 Current Indicator Values")
        if not ind_df.empty:
            latest = ind_df.iloc[-1]
            kpi_cols = st.columns(6)
            kpi_data = [
                ("RSI", f"{float(latest.get('rsi', 0) or 0):.1f}", "#FF6B35"),
                ("MACD", f"{float(latest.get('macd', 0) or 0):.4f}", "#4C9BE8"),
                ("ATR", f"{float(latest.get('atr', 0) or 0):.2f}", "#FFB830"),
            ]
            for i, (label, value, color) in enumerate(kpi_data):
                with kpi_cols[i]:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left:3px solid {color};">
                        <div style="color:#8B95A1;font-size:0.7rem;">{label}</div>
                        <div style="color:{color};font-family:'Space Mono',monospace;font-size:1.2rem;font-weight:700;">{value}</div>
                    </div>
                    """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Technical analysis error: {e}")
