import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.connection import get_engine
from dashboard.components.charts import _apply_theme
from config.coins import TRACKED_COINS


def render():
    st.markdown("## 🤖 AI Predictions")

    engine = get_engine()
    col1, col2 = st.columns([1, 1])
    with col1:
        coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="pred_coin")
    with col2:
        horizon = st.selectbox("Horizon", [1, 4, 24], format_func=lambda x: f"{x}h", key="pred_horizon")

    try:
        pred_df = pd.read_sql("""
            SELECT predicted_at, predicted_direction, confidence, model_name,
                   actual_direction, was_correct, predicted_price_change_pct
            FROM predictions
            WHERE coin = :coin AND horizon_hours = :horizon
            ORDER BY predicted_at DESC LIMIT 50
        """, engine, params={"coin": coin, "horizon": horizon})

        if not pred_df.empty:
            latest = pred_df.iloc[0]
            c1, c2, c3, c4 = st.columns(4)

            dir_color = "#00D4A8" if latest["predicted_direction"] == "UP" else "#FF4C4C"
            with c1:
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {dir_color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">PREDICTION</div>
                    <div style="color:{dir_color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">
                        {'▲ UP' if latest['predicted_direction'] == 'UP' else '▼ DOWN'}
                    </div>
                    <div style="color:#8B95A1;font-size:0.7rem;">{horizon}h Horizon</div>
                </div>
                """, unsafe_allow_html=True)

            with c2:
                conf_pct = float(latest["confidence"]) * 100
                conf_color = "#00D4A8" if conf_pct > 65 else "#FFB830" if conf_pct > 50 else "#FF4C4C"
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {conf_color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">CONFIDENCE</div>
                    <div style="color:{conf_color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{conf_pct:.0f}%</div>
                </div>
                """, unsafe_allow_html=True)

            with c3:
                completed = pred_df.dropna(subset=["was_correct"])
                accuracy = float(completed["was_correct"].mean()) * 100 if not completed.empty else 0
                acc_color = "#00D4A8" if accuracy > 60 else "#FFB830" if accuracy > 50 else "#FF4C4C"
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {acc_color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">HISTORICAL ACCURACY</div>
                    <div style="color:{acc_color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{accuracy:.1f}%</div>
                    <div style="color:#8B95A1;font-size:0.7rem;">{len(completed)} resolved predictions</div>
                </div>
                """, unsafe_allow_html=True)

            with c4:
                model = latest.get("model_name", "ensemble") or "ensemble"
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid #4C9BE8;">
                    <div style="color:#8B95A1;font-size:0.7rem;">MODEL</div>
                    <div style="color:#4C9BE8;font-family:'Space Mono',monospace;font-size:1rem;font-weight:700;">{str(model).upper()}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            fig = go.Figure()
            up_mask = pred_df["predicted_direction"] == "UP"
            fig.add_trace(go.Scatter(
                x=pred_df[up_mask]["predicted_at"], y=pred_df[up_mask]["confidence"],
                mode="markers", name="UP Predictions",
                marker=dict(color="#00D4A8", size=8, symbol="triangle-up"),
            ))
            fig.add_trace(go.Scatter(
                x=pred_df[~up_mask]["predicted_at"], y=pred_df[~up_mask]["confidence"],
                mode="markers", name="DOWN Predictions",
                marker=dict(color="#FF4C4C", size=8, symbol="triangle-down"),
            ))
            correct = pred_df.dropna(subset=["was_correct"])
            correct_mask = correct["was_correct"] == 1
            if correct_mask.any():
                fig.add_trace(go.Scatter(
                    x=correct[correct_mask]["predicted_at"], y=correct[correct_mask]["confidence"],
                    mode="markers", name="Correct",
                    marker=dict(color="#FFB830", size=12, symbol="star"),
                ))
            _apply_theme(fig, f"{coin} AI Prediction History ({horizon}h)")
            st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("No predictions yet. Predictions are generated during signal cycles.")

    except Exception as e:
        st.error(f"Predictions page error: {e}")
