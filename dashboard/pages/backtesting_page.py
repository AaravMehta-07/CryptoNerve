import streamlit as st
from backtesting.backtester import Backtester
from dashboard.components.charts import equity_curve_chart, _apply_theme
from config.coins import TRACKED_COINS
import plotly.graph_objects as go
import pandas as pd
from database.connection import get_engine


def render():
    st.markdown("## ⏳ Strategy Backtesting")
    st.info("Backtesting simulates historical trading using the composite signal strategy on stored historical signals.")

    col1, col2 = st.columns([1, 1])
    with col1:
        coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="bt_coin")
    with col2:
        days = st.selectbox("Period", [7, 14, 30, 60, 90], key="bt_days")

    if st.button("🚀 Run Backtest"):
        with st.spinner("Running backtest..."):
            backtester = Backtester()
            result = backtester.run_backtest(coin, days)

            if result is None or "message" in result:
                st.warning(result["message"] if result else "Not enough signal data for backtest. Let the pipeline run for a few cycles first.")
                return

            c1, c2, c3, c4 = st.columns(4)
            return_color = "#00D4A8" if result["total_return_pct"] > 0 else "#FF4C4C"

            with c1:
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {return_color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">TOTAL RETURN</div>
                    <div style="color:{return_color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{result['total_return_pct']:+.2f}%</div>
                    <div style="color:#8B95A1;font-size:0.75rem;">${result['initial_capital']:,.0f} → ${result['final_capital']:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                sharpe_color = "#00D4A8" if result["sharpe_ratio"] > 1 else "#FFB830" if result["sharpe_ratio"] > 0 else "#FF4C4C"
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {sharpe_color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">SHARPE RATIO</div>
                    <div style="color:{sharpe_color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{result['sharpe_ratio']:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid #FFB830;">
                    <div style="color:#8B95A1;font-size:0.7rem;">WIN RATE</div>
                    <div style="color:#FFB830;font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{result['win_rate']:.1f}%</div>
                    <div style="color:#8B95A1;font-size:0.75rem;">{result['total_trades']} trades</div>
                </div>
                """, unsafe_allow_html=True)
            with c4:
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid #FF4C4C;">
                    <div style="color:#8B95A1;font-size:0.7rem;">MAX DRAWDOWN</div>
                    <div style="color:#FF4C4C;font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">-{result['max_drawdown_pct']:.2f}%</div>
                </div>
                """, unsafe_allow_html=True)

            st.plotly_chart(equity_curve_chart(result["equity_curve"], f"{coin} Portfolio Equity"), use_container_width=True)

            if result["trades"]:
                st.markdown("### 📋 Trade Log")
                trades_df = pd.DataFrame(result["trades"])
                trades_df["result"] = trades_df["pnl"].apply(lambda x: "✅ WIN" if x > 0 else "❌ LOSS")
                st.dataframe(trades_df[["entry_time", "exit_time", "entry_price", "exit_price", "pnl", "pnl_pct", "result"]].style.applymap(
                    lambda v: "color: #00D4A8" if "WIN" in str(v) else ("color: #FF4C4C" if "LOSS" in str(v) else ""),
                    subset=["result"]
                ), use_container_width=True)
