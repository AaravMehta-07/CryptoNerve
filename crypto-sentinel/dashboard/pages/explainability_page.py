import streamlit as st
from config.coins import TRACKED_COINS
import base64

# SHAP is optional — requires trained XGBoost model
try:
    from explainability.shap_explainer import SHAPExplainer
    _HAS_SHAP = True
except ImportError:
    _HAS_SHAP = False
except Exception:
    _HAS_SHAP = False


def render():
    st.markdown("## 🔍 Model Explainability (SHAP)")
    st.info("SHAP (SHapley Additive exPlanations) shows which features drive the XGBoost model's predictions.")

    if not _HAS_SHAP:
        st.warning("SHAP explainability requires the `shap` package and a trained XGBoost model. Run `pip install shap` and train models to enable this page.")
        return

    coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="shap_coin")
    horizon = st.selectbox("Horizon", ["1h", "4h", "24h"], key="shap_horizon")

    if st.button("🔍 Generate SHAP Explanation"):
        with st.spinner("Computing SHAP values... this may take 30-60 seconds"):
            try:
                explainer = SHAPExplainer()
                result = explainer.explain_prediction(coin, horizon)

                if result is None:
                    st.error("SHAP explanation failed. Ensure models are trained first.")
                    return

                st.markdown(f"""
                <div style="background:#0E1117;border:1px solid #2D3445;border-radius:8px;padding:16px;
                            font-family:'Space Mono',monospace;font-size:0.8rem;color:#00D4A8;">
                    {str(result['explanation_text']).replace(chr(10), '<br/>')}
                </div>
                """, unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Prediction Waterfall")
                    img_bytes = base64.b64decode(result["waterfall_plot_b64"])
                    st.image(img_bytes, use_column_width=True, caption="Feature impact on latest prediction")

                with col2:
                    st.markdown("#### Feature Importance Summary")
                    img_bytes2 = base64.b64decode(result["summary_plot_b64"])
                    st.image(img_bytes2, use_column_width=True, caption="SHAP summary (last 50 predictions)")

                st.markdown("#### Top Feature Impacts")
                for feature, impact in result["top_features"][:10]:
                    direction = "🟢 BULLISH" if impact > 0 else "🔴 BEARISH"
                    color = "#00D4A8" if impact > 0 else "#FF4C4C"
                    st.markdown(f"""
                    <div style="padding:6px 12px;margin:3px 0;background:#1A1F2E;border-radius:6px;border-left:3px solid {color};display:flex;justify-content:space-between;">
                        <span style="color:#E8EAED;font-size:0.8rem;">{feature}</span>
                        <span style="color:{color};font-family:'Space Mono',monospace;font-size:0.8rem;">{direction} ({impact:+.4f})</span>
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"SHAP error: {e}")
