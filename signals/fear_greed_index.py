import pandas as pd
import numpy as np
from datetime import datetime, timezone
from loguru import logger
from database.connection import get_engine
from config.constants import FEAR_GREED_ZONES


class FearGreedIndex:
    def __init__(self):
        self.engine = get_engine()

    def _normalize(self, value, min_val, max_val):
        if max_val == min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))

    def calculate(self):
        try:
            # 1. Sentiment Component (30%)
            sent_df = pd.read_sql("""
                SELECT AVG(avg_sentiment) as avg_sent, SUM(total_posts) as total_volume
                FROM sentiment_aggregated
                WHERE window_start > NOW() - INTERVAL '24 hours' AND window_size = '1h'
            """, self.engine)
            avg_sentiment = float(sent_df.iloc[0]["avg_sent"] or 0.5)
            social_volume = float(sent_df.iloc[0]["total_volume"] or 0)
            sentiment_component = avg_sentiment
            social_volume_component = self._normalize(social_volume, 0, 500)

            # 2. Volume Momentum Component (20%)
            vol_df = pd.read_sql("""
                SELECT volume FROM price_data
                WHERE interval = '15m' AND timestamp > NOW() - INTERVAL '48 hours'
                ORDER BY timestamp DESC
            """, self.engine)
            if not vol_df.empty and len(vol_df) > 96:
                recent_vol = vol_df.head(96)["volume"].mean()
                older_vol = vol_df.tail(96)["volume"].mean()
                volume_change = (recent_vol - older_vol) / max(older_vol, 1)
                volume_momentum_component = self._normalize(volume_change, -0.5, 0.5)
            else:
                volume_momentum_component = 0.5

            # 3. Volatility Component (15%) — inverse
            price_df = pd.read_sql("""
                SELECT close FROM price_data
                WHERE coin = 'BTC' AND interval = '15m'
                AND timestamp > NOW() - INTERVAL '24 hours'
                ORDER BY timestamp ASC
            """, self.engine)
            if not price_df.empty and len(price_df) > 10:
                volatility = price_df["close"].pct_change().dropna().std()
                volatility_component = 1 - self._normalize(volatility, 0, 0.05)
            else:
                volatility_component = 0.5

            # 4. Whale Activity Component (15%)
            whale_df = pd.read_sql("""
                SELECT net_flow_usd, whale_activity_score FROM onchain_metrics
                WHERE timestamp > NOW() - INTERVAL '24 hours' ORDER BY timestamp DESC LIMIT 1
            """, self.engine)
            if not whale_df.empty:
                whale_activity_component = float(whale_df.iloc[0]["whale_activity_score"] or 0.5)
                net_flow = float(whale_df.iloc[0]["net_flow_usd"] or 0)
                whale_activity_component = min(whale_activity_component + (0.1 if net_flow > 0 else -0.1), 1.0)
                whale_activity_component = max(whale_activity_component, 0.0)
            else:
                whale_activity_component = 0.5

            # Weighted index
            index_value = (
                sentiment_component * 0.30
                + social_volume_component * 0.20
                + volume_momentum_component * 0.20
                + volatility_component * 0.15
                + whale_activity_component * 0.15
            )
            index_int = max(0, min(100, int(index_value * 100)))

            label = "Neutral"
            for (low, high), zone_label in FEAR_GREED_ZONES.items():
                if low <= index_int < high:
                    label = zone_label
                    break

            result = {
                "timestamp": datetime.now(timezone.utc),
                "index_value": index_int,
                "label": label,
                "sentiment_component": round(sentiment_component, 4),
                "social_volume_component": round(social_volume_component, 4),
                "volume_momentum_component": round(volume_momentum_component, 4),
                "volatility_component": round(volatility_component, 4),
                "whale_activity_component": round(whale_activity_component, 4),
            }

            try:
                pd.DataFrame([result]).to_sql(
                    "fear_greed_index", self.engine, if_exists="append", index=False
                )
            except Exception:
                pass

            return result
        except Exception as e:
            logger.error(f"Fear & Greed calculation error: {e}")
            return {"index_value": 50, "label": "Neutral",
                    "sentiment_component": 0.5, "social_volume_component": 0.5,
                    "volume_momentum_component": 0.5, "volatility_component": 0.5,
                    "whale_activity_component": 0.5}

    def get_history(self, hours=168):
        query = f"""
        SELECT timestamp, index_value, label FROM fear_greed_index
        WHERE timestamp > NOW() - INTERVAL '{hours} hours'
        ORDER BY timestamp ASC
        """
        try:
            return pd.read_sql(query, self.engine)
        except Exception:
            return pd.DataFrame()
