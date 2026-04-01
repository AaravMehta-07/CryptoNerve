import streamlit as st


def render_sidebar(pages):
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:12px 0;margin-bottom:16px;border-bottom:1px solid #2D3445;">
            <span style="font-size:2.5rem;">🛡️</span><br/>
            <span style="font-family:'Space Mono',monospace;font-size:0.65rem;color:#8B95A1;letter-spacing:2px;">
                CRYPTO SENTINEL v1.0
            </span>
        </div>
        """, unsafe_allow_html=True)

        selected = st.radio(
            "Navigation",
            pages,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("""
        <div style="padding:8px;background:#0D1025;border-radius:8px;border:1px solid #2D3445;">
            <p style="margin:0;font-size:0.7rem;color:#8B95A1;font-family:'Space Mono',monospace;">
                PIPELINE STATUS
            </p>
        </div>
        """, unsafe_allow_html=True)

        try:
            from database.connection import test_connection
            db_ok = test_connection()
        except Exception:
            db_ok = False

        status_color = "#00D4A8" if db_ok else "#FF4C4C"
        status_text = "ONLINE" if db_ok else "OFFLINE"
        st.markdown(f"""
        <div style="margin-top:8px;padding:8px 12px;background:#1A1F2E;border-radius:6px;border-left:3px solid {status_color};">
            <span style="font-family:'Space Mono',monospace;font-size:0.7rem;color:{status_color};">
                ● DB: {status_text}
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:24px;font-size:0.65rem;color:#5A6478;text-align:center;">
            ⚠️ Not financial advice<br/>Educational purposes only
        </div>
        """, unsafe_allow_html=True)

    return selected
