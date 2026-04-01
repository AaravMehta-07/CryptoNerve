import streamlit as st
import pandas as pd
import json
from database.connection import get_engine
from config.coins import TRACKED_COINS


def render():
    st.markdown("## ⚡ Trading Signals & Alerts")

    engine = get_engine()

    signal_colors = {
        "STRONG_BUY": "#00FF9C", "BUY": "#00D4A8",
        "HOLD": "#4C9BE8", "SELL": "#FF7B54", "STRONG_SELL": "#FF4C4C",
    }

    cols = st.columns(len(TRACKED_COINS))
    for i, (symbol, info) in enumerate(TRACKED_COINS.items()):
        with cols[i]:
            try:
                sig_df = pd.read_sql(f"""
                    SELECT signal_type, confidence, generated_at, reasoning,
                           sentiment_score, prediction_score, onchain_score, technical_score,
                           divergence_signal, price_at_signal
                    FROM signals WHERE coin = '{symbol}'
                    ORDER BY generated_at DESC LIMIT 1
                """, engine)

                if not sig_df.empty:
                    s = sig_df.iloc[0]
                    st_type = s["signal_type"]
                    color = signal_colors.get(st_type, "#8B95A1")
                    icon = {"STRONG_BUY": "🚀", "BUY": "📈", "HOLD": "⏸️", "SELL": "📉", "STRONG_SELL": "🔴"}.get(st_type, "")
                    st.markdown(f"""
                    <div style="padding:16px;background:#1A1F2E;border-radius:12px;border:2px solid {color};text-align:center;">
                        <div style="color:{info['color']};font-weight:700;margin-bottom:8px;">{symbol}</div>
                        <div style="color:{color};font-family:'Space Mono',monospace;font-size:1.2rem;font-weight:700;">{icon} {st_type}</div>
                        <div style="color:#E8EAED;font-size:1.1rem;font-weight:600;margin:6px 0;">${s['price_at_signal']:,.2f}</div>
                        <div style="background:#0E1117;border-radius:6px;padding:6px;margin-top:8px;">
                            <div style="color:#8B95A1;font-size:0.65rem;margin-bottom:4px;">COMPOSITE CONFIDENCE</div>
                            <div style="background:{color};height:6px;border-radius:3px;width:{s['confidence']*100:.0f}%;"></div>
                            <div style="color:{color};font-family:'Space Mono',monospace;font-size:0.85rem;margin-top:2px;">{s['confidence']:.0%}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info(f"No signal for {symbol}")
            except Exception as e:
                st.error(f"{symbol}: {e}")

    st.markdown("---")
    st.markdown("### 📋 Signal Detail & Reasoning")
    coin = st.selectbox("Select Coin", list(TRACKED_COINS.keys()), key="sig_detail_coin")

    try:
        detail_df = pd.read_sql(f"""
            SELECT signal_type, confidence, generated_at, reasoning,
                   sentiment_score, prediction_score, onchain_score, technical_score,
                   divergence_signal, price_at_signal
            FROM signals WHERE coin = '{coin}'
            ORDER BY generated_at DESC LIMIT 1
        """, engine)

        if not detail_df.empty:
            s = detail_df.iloc[0]
            st_type = s["signal_type"]
            color = signal_colors.get(st_type, "#8B95A1")

            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown("#### Component Scores")
                components = [
                    ("Sentiment", s.get("sentiment_score", 0), "#FF6B35"),
                    ("ML Prediction", s.get("prediction_score", 0), "#4C9BE8"),
                    ("On-Chain", s.get("onchain_score", 0), "#00D4A8"),
                    ("Technicals", s.get("technical_score", 0), "#FFB830"),
                ]
                for label, score, c in components:
                    score_f = float(score or 0)
                    st.markdown(f"""
                    <div style="margin:4px 0;padding:8px 12px;background:#1A1F2E;border-radius:6px;">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8B95A1;font-size:0.8rem;">{label}</span>
                            <span style="color:{c};font-family:'Space Mono',monospace;font-size:0.8rem;">{score_f:.2f}</span>
                        </div>
                        <div style="background:#0E1117;height:4px;border-radius:2px;margin-top:4px;">
                            <div style="background:{c};height:4px;border-radius:2px;width:{score_f*100:.0f}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                if s.get("divergence_signal") and s["divergence_signal"] != "NONE":
                    st.markdown(f"""
                    <div style="padding:8px 12px;background:#1A1F2E;border-radius:6px;border:1px solid #FF6B35;margin-top:8px;">
                        <span style="color:#FF6B35;font-size:0.8rem;">⚠️ {s['divergence_signal']}</span>
                    </div>
                    """, unsafe_allow_html=True)

            with c2:
                st.markdown("#### AI Reasoning")
                try:
                    reasons = json.loads(s["reasoning"]) if isinstance(s["reasoning"], str) else [s["reasoning"]]
                    reasoning_md = "\n".join([f"- {r}" for r in reasons])
                    st.markdown(f"""
                    <div style="background:#0E1117;border:1px solid #2D3445;border-radius:8px;padding:16px;font-family:'Space Mono',monospace;font-size:0.8rem;color:#00D4A8;white-space:pre-wrap;">
{reasoning_md}
                    </div>
                    """, unsafe_allow_html=True)
                except Exception:
                    st.text(str(s["reasoning"]))

    except Exception as e:
        st.error(f"Signal detail error: {e}")
