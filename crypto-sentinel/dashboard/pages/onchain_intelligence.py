import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from database.connection import get_engine
from database.sql_compat import time_ago
from dashboard.components.charts import _apply_theme
from config.coins import TRACKED_COINS


def render():
    st.markdown("## 🐋 On-Chain Intelligence")

    engine = get_engine()
    coin = st.selectbox("Coin", ["ETH", "BTC"], key="oc_coin")

    col1, col2 = st.columns([2, 1])

    with col1:
        try:
            cutoff = time_ago(hours=168)
            onchain_df = pd.read_sql("""
                SELECT timestamp, exchange_inflow_usd, exchange_outflow_usd, net_flow_usd,
                       whale_tx_count, whale_volume_usd
                FROM onchain_metrics
                WHERE coin = :coin AND window_size = '4h'
                AND timestamp >= :cutoff
                ORDER BY timestamp ASC
            """, engine, params={"coin": coin, "cutoff": cutoff})

            if not onchain_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=onchain_df["timestamp"], y=onchain_df["exchange_inflow_usd"] / 1e6,
                    name="Exchange Inflow ($M)", marker_color="#FF4C4C", opacity=0.8))
                fig.add_trace(go.Bar(x=onchain_df["timestamp"], y=onchain_df["exchange_outflow_usd"] / 1e6,
                    name="Exchange Outflow ($M)", marker_color="#00D4A8", opacity=0.8))
                _apply_theme(fig, f"{coin} Exchange Flows (USD Millions)")
                st.plotly_chart(fig, use_container_width=True)

                net_positive = onchain_df["net_flow_usd"] >= 0
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=onchain_df["timestamp"], y=onchain_df["net_flow_usd"] / 1e6,
                    name="Net Flow",
                    marker_color=[("#00D4A8" if v else "#FF4C4C") for v in net_positive],
                ))
                _apply_theme(fig2, f"{coin} Net Flow (Positive = Outflow/Accumulation)")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No on-chain data yet. Pipeline is collecting whale transactions.")
        except Exception as e:
            st.error(f"On-chain chart error: {e}")

    with col2:
        st.markdown("### 🔍 Latest Whale Txns")
        try:
            whale_df = pd.read_sql("""
                SELECT tx_hash, value_usd, tx_type, block_time AS timestamp,
                       is_exchange_from, is_exchange_to
                FROM whale_transactions
                WHERE token_symbol = :coin
                ORDER BY block_time DESC LIMIT 10
            """, engine, params={"coin": coin})

            for _, tx in whale_df.iterrows():
                tx_type = str(tx.get("tx_type", "transfer"))
                tx_color = {"exchange_inflow": "#FF4C4C", "exchange_outflow": "#00D4A8",
                            "transfer": "#4C9BE8"}.get(tx_type, "#8B95A1")
                icon = "🏦→🐋" if tx_type == "exchange_outflow" else "🐋→🏦" if tx_type == "exchange_inflow" else "🐋→🐋"
                val_usd = float(tx.get("value_usd", 0) or 0)
                ts_str = str(tx.get("timestamp", ""))[:16]
                st.markdown(f"""
                <div style="padding:6px 10px;margin:3px 0;background:#1A1F2E;border-radius:6px;border-left:3px solid {tx_color};">
                    <div style="color:{tx_color};font-family:'Space Mono',monospace;font-size:0.75rem;">{icon} ${val_usd:,.0f}</div>
                    <div style="color:#8B95A1;font-size:0.65rem;">{tx_type} · {ts_str}</div>
                </div>
                """, unsafe_allow_html=True)

            if whale_df.empty:
                st.info("Whale data loading...")
        except Exception as e:
            st.error(f"Whale tx error: {e}")

        st.markdown("---")
        st.markdown("### 📊 On-Chain Summary")
        try:
            latest_df = pd.read_sql("""
                SELECT net_flow_usd, whale_tx_count, whale_volume_usd, whale_activity_score
                FROM onchain_metrics WHERE coin = :coin
                ORDER BY timestamp DESC LIMIT 1
            """, engine, params={"coin": coin})
            if not latest_df.empty:
                r = latest_df.iloc[0]
                net = float(r.get("net_flow_usd", 0) or 0)
                accumulating = net > 0
                color = "#00D4A8" if accumulating else "#FF4C4C"
                score = float(r.get("whale_activity_score", 0.5) or 0.5)
                st.markdown(f"""
                <div class="metric-card">
                    <div style="color:#8B95A1;font-size:0.7rem;">WHALE SENTIMENT</div>
                    <div style="color:{color};font-size:1.2rem;font-weight:700;margin:6px 0;">
                        {'🟢 ACCUMULATING' if accumulating else '🔴 DISTRIBUTING'}
                    </div>
                    <div style="color:#8B95A1;font-size:0.75rem;">Net Flow: ${net/1e6:.2f}M</div>
                    <div style="color:#8B95A1;font-size:0.75rem;">Activity Score: {score:.2f}</div>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(str(e))
