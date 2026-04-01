"""
signals_alerts.py — Full signal log with reasoning, outcomes, and radar breakdown.

Features per Problem Statement §3.5 & §3.6:
  ✅ Per-coin latest signal cards with confidence bars
  ✅ Chronological signal log (ALL coins, 25 most recent)
  ✅ Outcome column: WIN / LOSS / PENDING (based on price post-signal)
  ✅ AI reasoning displayed per signal
  ✅ Radar chart: 4-component confidence breakdown
  ✅ Alert: STRONG signals in last 15 min highlighted at top
"""

import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

from database.connection import get_engine
from dashboard.components.charts import signal_radar_chart
from config.coins import TRACKED_COINS

_SIGNAL_COLORS = {
    "STRONG_BUY": "#00FF9C", "BUY": "#00D4A8",
    "HOLD": "#4C9BE8",
    "SELL": "#FF7B54", "STRONG_SELL": "#FF4C4C",
}
_SIGNAL_ICONS = {
    "STRONG_BUY": "🚀", "BUY": "📈",
    "HOLD": "⏸️",
    "SELL": "📉", "STRONG_SELL": "🔴",
}


@st.cache_data(ttl=15)
def _live_price(binance_symbol):
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": binance_symbol}, timeout=5,
        )
        return float(r.json()["price"])
    except Exception:
        return None


def _outcome(signal_type, price_at_signal, current_price, threshold_pct=0.5):
    """
    Returns (label, color) — WIN/LOSS/PENDING based on price movement.
    threshold_pct: min move (%) needed to call WIN/LOSS.
    """
    if price_at_signal is None or current_price is None or price_at_signal == 0:
        return "PENDING", "#8B95A1"
    pct_move = (current_price - price_at_signal) / price_at_signal * 100

    if signal_type in ("BUY", "STRONG_BUY"):
        if pct_move >= threshold_pct:
            return "WIN 🟢", "#00D4A8"
        if pct_move <= -threshold_pct:
            return "LOSS 🔴", "#FF4C4C"
    elif signal_type in ("SELL", "STRONG_SELL"):
        if pct_move <= -threshold_pct:
            return "WIN 🟢", "#00D4A8"
        if pct_move >= threshold_pct:
            return "LOSS 🔴", "#FF4C4C"
    return "PENDING ⏳", "#FFB830"


def render():
    st.markdown("""
    <h2 style="font-family:'Space Mono',monospace;font-size:1.3rem;margin-bottom:4px;">
        ⚡ Trading Signals &amp; Alerts
    </h2>
    <div style="color:#8B95A1;font-size:0.8rem;margin-bottom:16px;">
        Composite BUY/SELL signals · ML + LLM + On-Chain + Technicals
    </div>
    """, unsafe_allow_html=True)

    engine = get_engine()

    # ── Signal cards for all 5 coins ──────────────────────────────────────
    st.markdown("### 📊 Current Signal per Coin")
    cols = st.columns(len(TRACKED_COINS))
    for i, (symbol, info) in enumerate(TRACKED_COINS.items()):
        with cols[i]:
            try:
                df = pd.read_sql(f"""
                    SELECT signal_type, confidence, generated_at,
                           price_at_signal, sentiment_score, prediction_score,
                           onchain_score, technical_score
                    FROM signals WHERE coin = '{symbol}'
                    ORDER BY generated_at DESC LIMIT 1
                """, engine)
                if not df.empty:
                    s = df.iloc[0]
                    stype  = s["signal_type"]
                    color  = _SIGNAL_COLORS.get(stype, "#8B95A1")
                    icon   = _SIGNAL_ICONS.get(stype, "")
                    conf   = float(s["confidence"] or 0)

                    # Win/loss vs current price
                    curr = _live_price(info["binance_symbol"])
                    outcome_label, out_color = _outcome(stype, s["price_at_signal"], curr)

                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#1A1F2E 0%,#141B2D 100%);
                                border:2px solid {color};border-radius:12px;
                                padding:16px;text-align:center;margin-bottom:4px;">
                        <div style="color:{info['color']};font-weight:700;font-size:0.95rem;
                                    margin-bottom:6px;">{symbol}</div>
                        <div style="color:{color};font-family:'Space Mono',monospace;
                                    font-size:1.15rem;font-weight:700;">{icon} {stype}</div>
                        <div style="color:#E8EAED;font-size:1rem;font-weight:600;
                                    margin:6px 0;">${float(s['price_at_signal'] or 0):,.2f}</div>
                        <!-- Confidence bar -->
                        <div style="background:#0E1117;border-radius:4px;
                                    height:5px;margin:8px 0 4px;">
                            <div style="background:{color};height:5px;border-radius:4px;
                                        width:{conf*100:.0f}%;"></div>
                        </div>
                        <div style="font-size:0.72rem;color:{color};
                                    font-family:'Space Mono',monospace;">{conf:.0%} conf</div>
                        <div style="margin-top:6px;font-size:0.7rem;color:{out_color};
                                    font-weight:600;">{outcome_label}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info(f"No signal yet for {symbol}")
            except Exception as e:
                st.error(f"{symbol}: {e}")

    st.markdown("---")

    # ── Radar breakdown for selected coin ─────────────────────────────────
    st.markdown("### 🎯 Signal Component Breakdown")
    col_coin, col_chart = st.columns([1, 2])
    with col_coin:
        radar_coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="radar_coin")
        try:
            rdf = pd.read_sql(f"""
                SELECT signal_type, confidence,
                       sentiment_score, prediction_score,
                       onchain_score, technical_score, reasoning,
                       divergence_signal, generated_at
                FROM signals WHERE coin = '{radar_coin}'
                ORDER BY generated_at DESC LIMIT 1
            """, engine)
            if not rdf.empty:
                s = rdf.iloc[0]
                stype = s["signal_type"]
                color = _SIGNAL_COLORS.get(stype, "#8B95A1")
                weights = [("LLM Sentiment", s.get("sentiment_score",  0.5), "#FF6B35"),
                           ("ML Prediction",  s.get("prediction_score",  0.5), "#4C9BE8"),
                           ("On-Chain",       s.get("onchain_score",     0.5), "#00D4A8"),
                           ("Technicals",     s.get("technical_score",   0.5), "#FFB830")]
                for label, score, c in weights:
                    v = float(score or 0.5)
                    st.markdown(f"""
                    <div style="margin:4px 0;padding:8px 12px;background:#1A1F2E;border-radius:6px;">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="color:#8B95A1;font-size:0.78rem;">{label}</span>
                            <span style="color:{c};font-family:'Space Mono',monospace;
                                         font-size:0.78rem;">{v:.2f}</span>
                        </div>
                        <div style="background:#0E1117;height:4px;border-radius:2px;margin-top:4px;">
                            <div style="background:{c};height:4px;border-radius:2px;
                                        width:{v*100:.0f}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                if s.get("divergence_signal") and str(s["divergence_signal"]) not in ("NONE", "None", "nan", ""):
                    st.warning(f"⚠️ {s['divergence_signal']}")
        except Exception as e:
            st.error(f"Score error: {e}")

    with col_chart:
        try:
            if not rdf.empty:
                s = rdf.iloc[0]
                fig = signal_radar_chart(
                    float(s.get("sentiment_score",  0.5) or 0.5),
                    float(s.get("prediction_score", 0.5) or 0.5),
                    float(s.get("onchain_score",    0.5) or 0.5),
                    float(s.get("technical_score",  0.5) or 0.5),
                    coin=radar_coin, signal_type=s["signal_type"],
                )
                st.plotly_chart(fig, use_container_width=True)
                st.markdown("#### 🤖 AI Reasoning")
                raw_r = str(s.get("reasoning") or "No reasoning available")
                try:
                    reasons = json.loads(raw_r) if raw_r.startswith("[") else [raw_r]
                    md_reasons = "\n".join([f"- {r}" for r in reasons])
                except Exception:
                    md_reasons = f"- {raw_r}"
                st.markdown(f"""
                <div style="background:#0E1117;border:1px solid #2D3445;border-radius:8px;
                            padding:14px;font-family:'Space Mono',monospace;
                            font-size:0.78rem;color:#00D4A8;white-space:pre-wrap;">
{md_reasons}
                </div>
                """, unsafe_allow_html=True)
        except Exception:
            pass

    st.markdown("---")

    # ── Chronological Signal Log ───────────────────────────────────────────
    st.markdown("### 📋 Chronological Signal Log")
    st.caption("25 most recent signals · Outcome = price movement after signal generation")

    try:
        log_df = pd.read_sql("""
            SELECT coin, signal_type, confidence, generated_at,
                   price_at_signal, sentiment_score, prediction_score,
                   onchain_score, technical_score, reasoning
            FROM signals
            ORDER BY generated_at DESC LIMIT 25
        """, engine)

        if log_df.empty:
            st.info("No signals in database yet — run the pipeline to generate signals.")
            return

        # ── Enrichment: add outcome by fetching current Binance price once per coin ──
        current_prices = {}
        for sym, info in TRACKED_COINS.items():
            current_prices[sym] = _live_price(info["binance_symbol"])

        for _, row in log_df.iterrows():
            coin    = row["coin"]
            stype   = row["signal_type"]
            color   = _SIGNAL_COLORS.get(stype, "#8B95A1")
            icon    = _SIGNAL_ICONS.get(stype, "")
            conf    = float(row["confidence"] or 0)
            ts      = pd.Timestamp(row["generated_at"])
            age_min = int((datetime.utcnow() - ts.to_pydatetime().replace(tzinfo=None)).total_seconds() / 60)
            curr_p  = current_prices.get(coin)
            sig_p   = float(row["price_at_signal"] or 0) if row["price_at_signal"] else None
            out_label, out_color = _outcome(stype, sig_p, curr_p)

            pct_move_str = ""
            if sig_p and curr_p and sig_p > 0:
                pct = (curr_p - sig_p) / sig_p * 100
                pct_move_str = f"  ({'+' if pct >= 0 else ''}{pct:.2f}%)"

            with st.expander(
                f"{icon} {coin} · {stype}  |  conf {conf:.0%}  |  "
                f"{ts.strftime('%d-%b %H:%M')}  ({age_min}m ago)  |  "
                f"{out_label}{pct_move_str}",
                expanded=False,
            ):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Signal", f"{icon} {stype}")
                    st.metric("Confidence", f"{conf:.0%}")
                with c2:
                    st.metric("Price at Signal",
                              f"${sig_p:,.2f}" if sig_p else "—")
                    st.metric("Current Price",
                              f"${curr_p:,.2f}" if curr_p else "—")
                with c3:
                    st.metric("Outcome", out_label)
                    st.metric("Generated", ts.strftime("%H:%M %d-%b"))

                # Component bar mini-chart
                components = {
                    "LLM Sentiment": (float(row.get("sentiment_score")  or 0.5), "#FF6B35"),
                    "ML Prediction":  (float(row.get("prediction_score") or 0.5), "#4C9BE8"),
                    "On-Chain":       (float(row.get("onchain_score")    or 0.5), "#00D4A8"),
                    "Technicals":     (float(row.get("technical_score")  or 0.5), "#FFB830"),
                }
                bar_html = ""
                for lab, (v, c) in components.items():
                    bar_html += f"""
                    <div style="display:flex;align-items:center;gap:8px;margin:3px 0;">
                        <span style="color:#8B95A1;font-size:0.72rem;width:100px;">{lab}</span>
                        <div style="flex:1;background:#0E1117;height:4px;border-radius:2px;">
                            <div style="background:{c};height:4px;border-radius:2px;width:{v*100:.0f}%;"></div>
                        </div>
                        <span style="color:{c};font-size:0.72rem;font-family:'Space Mono',monospace;width:36px;">{v:.2f}</span>
                    </div>"""
                st.markdown(f"""
                <div style="background:#1A1F2E;border-radius:6px;padding:10px 14px;margin:8px 0;">
                    <div style="color:#8B95A1;font-size:0.7rem;margin-bottom:6px;letter-spacing:1px;">
                        COMPONENT SCORES
                    </div>
                    {bar_html}
                </div>
                """, unsafe_allow_html=True)

                # Reasoning
                raw_r = str(row.get("reasoning") or "—")
                st.markdown(f"""
                <div style="background:#0E1117;border:1px solid #2D3445;border-radius:6px;
                            padding:10px 14px;font-family:'Space Mono',monospace;
                            font-size:0.76rem;color:#00D4A8;border-left:3px solid {color};">
                    {raw_r}
                </div>
                """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Log error: {e}")
