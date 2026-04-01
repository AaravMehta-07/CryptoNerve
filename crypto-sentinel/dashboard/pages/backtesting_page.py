import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.connection import get_engine
from dashboard.components.charts import equity_curve_chart
from config.coins import TRACKED_COINS

try:
    from backtesting.backtester import Backtester
    _HAS_BACKTESTER = True
except Exception:
    _HAS_BACKTESTER = False


def render():
    st.markdown("## ⏳ Strategy Backtesting")
    st.info("Backtesting simulates historical trading using the composite signal strategy on stored historical signals.")

    col1, col2 = st.columns([1, 1])
    with col1:
        coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="bt_coin")
    with col2:
        days = st.selectbox("Period", [7, 14, 30, 60, 90], key="bt_days")

    if st.button("🚀 Run Backtest"):
        if not _HAS_BACKTESTER:
            st.error("Backtester not available.")
            return

        with st.spinner("Running backtest..."):
            try:
                backtester = Backtester()
                result = backtester.run_backtest(coin, days)

                if result is None or "message" in result:
                    st.warning(result["message"] if result and "message" in result
                               else "Not enough signal data for backtest. Let the pipeline run for a few cycles first.")
                    return

                c1, c2, c3, c4 = st.columns(4)
                return_color = "#00D4A8" if result["total_return_pct"] > 0 else "#FF4C4C"

                kpis = [
                    (c1, "TOTAL RETURN", f"{result['total_return_pct']:+.2f}%",
                     f"${result['initial_capital']:,.0f} → ${result['final_capital']:,.0f}", return_color),
                    (c2, "SHARPE RATIO", f"{result['sharpe_ratio']:.2f}", None,
                     "#00D4A8" if result["sharpe_ratio"] > 1 else "#FFB830" if result["sharpe_ratio"] > 0 else "#FF4C4C"),
                    (c3, "WIN RATE", f"{result['win_rate']:.1f}%", f"{result['total_trades']} trades", "#FFB830"),
                    (c4, "MAX DRAWDOWN", f"-{result['max_drawdown_pct']:.2f}%", None, "#FF4C4C"),
                ]
                for col, label, val, subtext, color in kpis:
                    sub = f'<div style="color:#8B95A1;font-size:0.75rem;">{subtext}</div>' if subtext else ""
                    with col:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left:3px solid {color};">
                            <div style="color:#8B95A1;font-size:0.7rem;">{label}</div>
                            <div style="color:{color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{val}</div>
                            {sub}
                        </div>
                        """, unsafe_allow_html=True)

                if result.get("equity_curve"):
                    st.plotly_chart(equity_curve_chart(result["equity_curve"], f"{coin} Portfolio Equity"), use_container_width=True)

                if result.get("trades"):
                    st.markdown("### 📋 Trade Log")
                    trades_df = pd.DataFrame(result["trades"])
                    trades_df["result"] = trades_df["pnl"].apply(lambda x: "✅ WIN" if x > 0 else "❌ LOSS")
                    display_cols = [c for c in ["entry_time","exit_time","entry_price","exit_price","pnl","pnl_pct","result"] if c in trades_df.columns]
                    st.dataframe(trades_df[display_cols], use_container_width=True)
            except Exception as e:
                st.error(f"Backtest error: {e}")
