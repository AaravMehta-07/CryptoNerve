import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.connection import get_engine
from dashboard.components.charts import prediction_accuracy_bar, _apply_theme
from models.accuracy_tracker import AccuracyTracker


def render():
    st.markdown("## 📊 Model Performance Tracker")

    engine = get_engine()
    tracker = AccuracyTracker()

    overall = tracker.get_overall_metrics()
    if not overall.empty and overall.iloc[0]["total_predictions"] > 0:
        r = overall.iloc[0]
        cols = st.columns(4)
        metrics = [
            ("TOTAL PREDICTIONS", int(r["total_predictions"]), "#4C9BE8"),
            ("CORRECT", int(r["correct"]), "#00D4A8"),
            ("OVERALL ACCURACY", f"{r['accuracy']*100:.1f}%", "#FF6B35"),
            ("AVG CONFIDENCE", f"{r['avg_confidence']*100:.1f}%", "#FFB830"),
        ]
        for col, (label, val, color) in zip(cols, metrics):
            with col:
                st.markdown(f"""
                <div class="metric-card" style="border-left:3px solid {color};">
                    <div style="color:#8B95A1;font-size:0.7rem;">{label}</div>
                    <div style="color:{color};font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;">{val}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No completed predictions yet. Predictions are evaluated after their horizon passes.")

    st.markdown("---")
    accuracy_df = tracker.get_model_accuracy()
    if not accuracy_df.empty:
        st.plotly_chart(prediction_accuracy_bar(accuracy_df), use_container_width=True)

        st.markdown("### 📋 Full Accuracy Table")
        styled_df = accuracy_df.copy()
        styled_df["accuracy_pct"] = (styled_df["accuracy"] * 100).round(1).astype(str) + "%"
        st.dataframe(
            styled_df[["model_name", "coin", "horizon_hours", "accuracy_pct",
                        "avg_confidence", "total_predictions"]],
            use_container_width=True,
        )
    else:
        st.info("Accuracy data will populate once predictions are resolved.")

    st.markdown("---")
    st.markdown("### ⏱️ Recent Prediction Outcomes")
    try:
        pred_df = pd.read_sql("""
            SELECT coin, model_name, horizon_hours, predicted_direction,
                   confidence, actual_direction, was_correct, outcome_recorded_at
            FROM predictions
            WHERE was_correct IS NOT NULL
            ORDER BY outcome_recorded_at DESC LIMIT 50
        """, engine)

        if not pred_df.empty:
            pred_df["result"] = pred_df["was_correct"].apply(lambda x: "✅" if x else "❌")
            pred_df["confidence_fmt"] = (pred_df["confidence"] * 100).round(1).astype(str) + "%"
            st.dataframe(
                pred_df[["coin", "model_name", "horizon_hours", "predicted_direction",
                          "actual_direction", "confidence_fmt", "result"]],
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Outcomes error: {e}")
