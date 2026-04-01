import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.connection import get_engine
from database.sql_compat import time_ago
from dashboard.components.charts import sentiment_time_series, _apply_theme
from config.coins import TRACKED_COINS

# WordCloud is optional
try:
    from wordcloud import WordCloud
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io, base64
    _HAS_WORDCLOUD = True
except ImportError:
    _HAS_WORDCLOUD = False


def render():
    st.markdown("## 💬 Sentiment Analysis")

    engine = get_engine()
    coin = st.selectbox("Coin", list(TRACKED_COINS.keys()), key="sa_coin")

    col1, col2 = st.columns([3, 1])

    with col1:
        try:
            cutoff = time_ago(hours=168)
            sent_df = pd.read_sql("""
                SELECT window_start, avg_sentiment, bullish_count, bearish_count,
                       neutral_count, fud_count, total_posts, sentiment_velocity
                FROM sentiment_aggregated
                WHERE coin = :coin AND window_size = '1h'
                AND window_start >= :cutoff
                ORDER BY window_start ASC
            """, engine, params={"coin": coin, "cutoff": cutoff})

            if not sent_df.empty:
                st.plotly_chart(sentiment_time_series(sent_df, coin), use_container_width=True)

                fig = go.Figure()
                x = sent_df["window_start"]
                for label, color in [("bullish_count", "#00D4A8"), ("bearish_count", "#FF4C4C"),
                                       ("neutral_count", "#4C9BE8"), ("fud_count", "#FFB830")]:
                    if label in sent_df.columns and sent_df[label].sum() > 0:
                        fig.add_trace(go.Bar(x=x, y=sent_df[label], name=label.split("_")[0].title(),
                                             marker_color=color, opacity=0.8))
                fig.update_layout(barmode="stack")
                _apply_theme(fig, "Sentiment Composition by Type")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No sentiment data yet. Pipeline is collecting and analyzing posts.")
        except Exception as e:
            st.error(f"Sentiment chart error: {e}")

    with col2:
        st.markdown("### 📊 Sentiment Stats")
        try:
            recent = pd.read_sql("""
                SELECT avg_sentiment, bullish_count, bearish_count, neutral_count,
                       fud_count, total_posts, sentiment_velocity
                FROM sentiment_aggregated
                WHERE coin = :coin AND window_size = '4h'
                ORDER BY window_start DESC LIMIT 1
            """, engine, params={"coin": coin})
            if not recent.empty:
                r = recent.iloc[0]
                sent = float(r["avg_sentiment"])
                color = "#00D4A8" if sent > 0.6 else "#FF4C4C" if sent < 0.4 else "#FFB830"
                st.markdown(f"""
                <div class="metric-card">
                    <div style="color:#8B95A1;font-size:0.7rem;">CURRENT SENTIMENT</div>
                    <div style="color:{color};font-family:'Space Mono',monospace;font-size:2rem;font-weight:700;">{sent:.2f}</div>
                    <div style="color:#8B95A1;font-size:0.75rem;">{'Bullish 🟢' if sent > 0.6 else 'Bearish 🔴' if sent < 0.4 else 'Neutral ⚪'}</div>
                </div>
                """, unsafe_allow_html=True)

                total = max(int(r.get("total_posts", 1) or 1), 1)
                for label, count, clr in [
                    ("🟢 Bullish", int(r.get("bullish_count", 0) or 0), "#00D4A8"),
                    ("🔴 Bearish", int(r.get("bearish_count", 0) or 0), "#FF4C4C"),
                    ("⚪ Neutral", int(r.get("neutral_count", 0) or 0), "#4C9BE8"),
                    ("⚠️ FUD",    int(r.get("fud_count",     0) or 0), "#FFB830"),
                ]:
                    pct = count / total * 100
                    st.markdown(f"""
                    <div style="margin:4px 0;padding:4px 8px;background:#1A1F2E;border-radius:4px;border-left:2px solid {clr};">
                        <span style="color:{clr};font-size:0.8rem;">{label}</span>
                        <span style="color:#8B95A1;font-size:0.75rem;float:right;">{count} ({pct:.0f}%)</span>
                    </div>
                    """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Stats error: {e}")

    st.markdown("---")
    st.markdown("### 🔥 Top Narratives")
    try:
        cutoff24 = time_ago(hours=24)
        narratives_df = pd.read_sql("""
            SELECT narrative, SUM(mention_count) as mentions FROM narrative_tracking
            WHERE coin = :coin AND source_type IN ('reddit', 'news')
            AND timestamp >= :cutoff
            GROUP BY narrative ORDER BY mentions DESC LIMIT 15
        """, engine, params={"coin": coin, "cutoff": cutoff24})

        if not narratives_df.empty:
            fig = go.Figure(go.Bar(
                x=narratives_df["mentions"], y=narratives_df["narrative"],
                orientation="h", marker_color="#FF6B35",
            ))
            _apply_theme(fig, "Top Crypto Narratives (24h)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Narrative data will appear after pipeline runs.")
    except Exception as e:
        st.error(f"Narrative error: {e}")
