import streamlit as st
from datetime import datetime


def render_header():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;padding:8px 0 16px 0;border-bottom:1px solid #2D3445;margin-bottom:20px;">
        <span style="font-size:2rem;">🛡️</span>
        <div>
            <h1 style="margin:0;font-size:1.6rem;font-weight:700;background:linear-gradient(135deg,#FF6B35,#FF9A00);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                CRYPTO SENTINEL
            </h1>
            <p style="margin:0;font-size:0.75rem;color:#8B95A1;font-family:'Space Mono',monospace;letter-spacing:2px;">
                LLM-POWERED MARKET INTELLIGENCE TERMINAL
            </p>
        </div>
        <div style="margin-left:auto;text-align:right;">
            <span style="font-size:0.7rem;color:#8B95A1;font-family:'Space Mono',monospace;">
                LIVE · {time}
            </span>
        </div>
    </div>
    """.format(time=datetime.now().strftime("%H:%M:%S")), unsafe_allow_html=True)
