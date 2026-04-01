import streamlit as st
from datetime import datetime


def render_header():
    now = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:14px;padding:10px 0 14px 0;">
        <!-- Shield icon with glow -->
        <div style="width:44px;height:44px;background:linear-gradient(135deg,#FF6B35,#FF3D00);
                    border-radius:10px;display:flex;align-items:center;justify-content:center;
                    box-shadow:0 4px 16px rgba(255,107,53,0.4);flex-shrink:0;font-size:22px;">
            🛡️
        </div>
        <!-- Title block -->
        <div style="flex:1;">
            <h1 style="margin:0;font-size:1.45rem;font-weight:800;letter-spacing:0.5px;
                       background:linear-gradient(135deg,#FFFFFF 0%,#A0AEC0 100%);
                       -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                CRYPTO SENTINEL
            </h1>
            <p style="margin:0;font-size:0.68rem;color:#4A5568;
                      font-family:'Space Mono',monospace;letter-spacing:2.5px;margin-top:1px;">
                SELF&#8209;HOSTED LLM INTELLIGENCE TERMINAL &nbsp;·&nbsp; NMIMS INNOVATHON 2026
            </p>
        </div>
        <!-- Live indicator + time -->
        <div style="text-align:right;flex-shrink:0;">
            <div style="display:flex;align-items:center;gap:6px;justify-content:flex-end;">
                <div style="width:7px;height:7px;background:#00FF9C;border-radius:50%;
                            box-shadow:0 0 8px #00FF9C;
                            animation:pulse 2s ease-in-out infinite;"></div>
                <span style="font-family:'Space Mono',monospace;font-size:0.68rem;
                             color:#00D4A8;font-weight:700;letter-spacing:1px;">LIVE</span>
            </div>
            <div style="font-family:'Space Mono',monospace;font-size:0.65rem;
                        color:#4A5568;margin-top:2px;">{now} IST</div>
        </div>
    </div>
    <style>
    @keyframes pulse {{
        0%,100% {{ opacity:1; transform:scale(1); }}
        50%      {{ opacity:0.5; transform:scale(1.3); }}
    }}
    </style>
    """, unsafe_allow_html=True)
