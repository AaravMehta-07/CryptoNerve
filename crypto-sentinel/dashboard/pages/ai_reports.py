import streamlit as st
from database.connection import get_engine
from database.sql_compat import time_ago
from config.coins import TRACKED_COINS
import pandas as pd

# LLM report generator — optional (requires sentient/llm)
try:
    from reports.llm_report_generator import LLMReportGenerator
    _generator = LLMReportGenerator()
    _HAS_LLM = True
except Exception:
    _generator = None
    _HAS_LLM = False


def render():
    st.markdown("## 📝 AI Market Intelligence Reports")

    if not _HAS_LLM:
        st.warning("LLM report generator not available. Showing historical reports only.")

    engine = get_engine()

    col1, col2 = st.columns([2, 1])
    with col1:
        coin = st.selectbox("Coin to Analyze", list(TRACKED_COINS.keys()), key="rep_coin")
    with col2:
        report_type = st.selectbox("Report Type", ["Coin Analysis", "Market Overview", "Signal Explanation"], key="rep_type")

    if st.button("🤖 Generate Report"):
        if not _HAS_LLM:
            st.error("LLM not available. Install llama-cpp-python and download mistral.gguf to enable.")
        else:
            with st.spinner("🤖 Mistral 7B is analyzing the data..."):
                report = _run_report(engine, _generator, report_type, coin)
                if report:
                    st.markdown(f"""
                    <div style="background:#0E1117;border:1px solid #2D3445;border-radius:12px;padding:24px;
                                font-family:'Inter',sans-serif;line-height:1.7;color:#E8EAED;">
                        {str(report).replace(chr(10), '<br/>')}
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📚 Historical Reports")
    try:
        hist_df = pd.read_sql("""
            SELECT coin, report_type, model_used, generated_at,
                   SUBSTR(report_text, 1, 200) as preview
            FROM market_reports ORDER BY generated_at DESC LIMIT 10
        """, engine)
        if not hist_df.empty:
            for _, r in hist_df.iterrows():
                label = str(r.get("coin") or "ALL")
                rtype = str(r.get("report_type") or "")
                ts = str(r.get("generated_at") or "")[:16]
                with st.expander(f"📄 {label} — {rtype} — {ts}"):
                    st.text(str(r.get("preview", "")) + "...")
        else:
            st.info("No reports generated yet.")
    except Exception as e:
        st.error(f"Historical reports error: {e}")


def _run_report(engine, generator, report_type, coin):
    try:
        if report_type == "Coin Analysis":
            price_df = pd.read_sql("""
                SELECT close FROM price_data WHERE coin = :coin
                ORDER BY timestamp DESC LIMIT 2
            """, engine, params={"coin": coin})
            current_price = float(price_df.iloc[0]["close"]) if not price_df.empty else 0
            prev_price = float(price_df.iloc[1]["close"]) if len(price_df) > 1 else current_price
            change_24h = (current_price - prev_price) / max(prev_price, 1) * 100

            sent_df = pd.read_sql("""
                SELECT avg_sentiment, sentiment_velocity FROM sentiment_aggregated
                WHERE coin = :coin AND window_size = '4h' ORDER BY window_start DESC LIMIT 1
            """, engine, params={"coin": coin})
            sentiment = float(sent_df.iloc[0]["avg_sentiment"]) if not sent_df.empty else 0.5

            ind_df = pd.read_sql("""
                SELECT rsi, macd_signal FROM technical_indicators
                WHERE coin = :coin ORDER BY timestamp DESC LIMIT 1
            """, engine, params={"coin": coin})

            signal_df = pd.read_sql("""
                SELECT signal_type, confidence FROM signals
                WHERE coin = :coin ORDER BY generated_at DESC LIMIT 1
            """, engine, params={"coin": coin})

            fg_df = pd.read_sql(
                "SELECT index_value, label FROM fear_greed_index ORDER BY timestamp DESC LIMIT 1",
                engine
            )

            coin_data = {
                "symbol": coin, "name": TRACKED_COINS[coin]["name"],
                "price": f"{current_price:,.2f}",
                "change_24h": f"{change_24h:.2f}",
                "sentiment": f"{sentiment:.2f}",
                "fear_greed": str(fg_df.iloc[0]["index_value"]) if not fg_df.empty else "N/A",
                "rsi": f"{float(ind_df.iloc[0]['rsi']):.1f}" if not ind_df.empty else "N/A",
                "macd_signal": f"{float(ind_df.iloc[0]['macd_signal']):.4f}" if not ind_df.empty else "N/A",
                "signal": str(signal_df.iloc[0]["signal_type"]) if not signal_df.empty else "N/A",
                "confidence": f"{float(signal_df.iloc[0]['confidence']):.0%}" if not signal_df.empty else "N/A",
            }
            return generator.generate_coin_report(coin_data)

        elif report_type == "Market Overview":
            return generator.generate_market_overview()
        else:
            sig_df = pd.read_sql("""
                SELECT coin, signal_type, confidence, reasoning
                FROM signals WHERE coin = :coin ORDER BY generated_at DESC LIMIT 1
            """, engine, params={"coin": coin})
            if not sig_df.empty:
                return generator.generate_signal_explanation(sig_df.iloc[0].to_dict())
            return "No recent signal found."
    except Exception as e:
        return f"Report generation error: {e}"
