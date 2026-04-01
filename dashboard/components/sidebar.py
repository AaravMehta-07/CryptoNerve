"""
Updated sidebar with live DB status, signal count, and news source status.
"""
import streamlit as st
from datetime import datetime


def render_sidebar(pages):
    with st.sidebar:
        # Logo & branding
        st.markdown("""
        <div style="text-align:center;padding:16px 0 12px;border-bottom:1px solid #2D3445;">
            <span style="font-size:2.8rem;">🛡️</span><br/>
            <span style="font-family:'Space Mono',monospace;font-size:0.65rem;
                         color:#8B95A1;letter-spacing:2.5px;">
                CRYPTO SENTINEL
            </span><br/>
            <span style="font-size:0.6rem;color:#5A6478;">v1.0  ·  LLM Intelligence Terminal</span>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        selected = st.radio(
            "Navigation",
            pages,
            label_visibility="collapsed",
        )

        st.markdown("---")

        # ── Pipeline Status ────────────────────────────────────────────────
        st.markdown("""
        <p style="margin:0 0 6px;font-size:0.7rem;color:#8B95A1;
                  font-family:'Space Mono',monospace;letter-spacing:1px;">
            PIPELINE STATUS
        </p>
        """, unsafe_allow_html=True)

        # DB connectivity
        try:
            from database.connection import test_connection
            db_ok = test_connection()
        except Exception:
            db_ok = False

        db_color = "#00D4A8" if db_ok else "#FF4C4C"
        db_text  = "ONLINE" if db_ok else "OFFLINE"

        # Signal count (last 24h)
        sig_count = 0
        news_count = 0
        if db_ok:
            try:
                from database.connection import get_engine
                import pandas as pd
                eng = get_engine()
                sig_count  = pd.read_sql("SELECT COUNT(*) as c FROM signals WHERE generated_at > NOW() - INTERVAL '24 hours'", eng).iloc[0]["c"]
                news_count = pd.read_sql("SELECT COUNT(*) as c FROM news_articles WHERE published_at > NOW() - INTERVAL '24 hours'", eng).iloc[0]["c"]
            except Exception:
                pass

        # Render status pills
        status_items = [
            ("● DB", db_text, db_color),
            ("📡 Signals (24h)", str(sig_count), "#4C9BE8"),
            ("📰 News (24h)", str(news_count), "#FF6B35"),
        ]
        for label, val, color in status_items:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:6px 10px;margin:3px 0;background:#1A1F2E;
                        border-radius:6px;border-left:3px solid {color};">
                <span style="font-family:'Space Mono',monospace;font-size:0.68rem;
                              color:#8B95A1;">{label}</span>
                <span style="font-family:'Space Mono',monospace;font-size:0.68rem;
                              color:{color};font-weight:700;">{val}</span>
            </div>
            """, unsafe_allow_html=True)

        # ── News sources status ────────────────────────────────────────────
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown("""
        <p style="margin:0 0 6px;font-size:0.7rem;color:#8B95A1;
                  font-family:'Space Mono',monospace;letter-spacing:1px;">
            NEWS SOURCES
        </p>
        """, unsafe_allow_html=True)

        sources = [
            ("CoinDesk",        "RSS"),
            ("CoinTelegraph",   "RSS"),
            ("Crypto Briefing", "RSS"),
            ("The Block",       "RSS"),
            ("Google News",     "RSS"),
            ("NewsAPI",         "API"),
        ]
        for name, stype in sources:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:4px 8px;
                        margin:2px 0;background:#13182A;border-radius:4px;">
                <span style="color:#8B95A1;font-size:0.65rem;">{name}</span>
                <span style="color:#00D4A8;font-size:0.6rem;
                              font-family:'Space Mono',monospace;">✓ {stype}</span>
            </div>
            """, unsafe_allow_html=True)

        # ── Disclaimer ────────────────────────────────────────────────────
        st.markdown("""
        <div style="margin-top:20px;padding:8px 10px;background:#0D1025;border-radius:6px;
                    border:1px solid #2D3445;text-align:center;">
            <span style="font-size:0.6rem;color:#5A6478;">
                ⚠️ Simulation only · Not financial advice<br/>
                Educational use · NMIMS INNOVATHON 2026
            </span>
        </div>
        """, unsafe_allow_html=True)

    return selected
