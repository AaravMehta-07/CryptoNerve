import pandas as pd
from loguru import logger
from database.connection import get_engine
from database.sql_compat import time_ago


class SentimentMomentum:
    def __init__(self):
        self.engine = get_engine()

    def calculate(self, coin, window_hours=24):
        cutoff = time_ago(hours=window_hours)
        query = """
        SELECT avg_sentiment, window_start
        FROM sentiment_aggregated
        WHERE coin = :coin AND window_size = '1h'
        AND window_start >= :cutoff
        ORDER BY window_start ASC
        """
        try:
            df = pd.read_sql(query, self.engine, params={"coin": coin, "cutoff": cutoff})
            if df.empty or len(df) < 6:
                return {
                    "current": 0.5, "velocity": 0.0, "acceleration": 0.0,
                    "signal": "NEUTRAL", "description": "Insufficient data",
                }

            sentiment = df["avg_sentiment"]
            velocity = sentiment.diff()
            acceleration = velocity.diff()

            current = float(sentiment.iloc[-1])
            vel = float(velocity.iloc[-1]) if not pd.isna(velocity.iloc[-1]) else 0.0
            acc = float(acceleration.iloc[-1]) if not pd.isna(acceleration.iloc[-1]) else 0.0

            if vel > 0.02 and acc > 0:
                signal, desc = "MOMENTUM_BUY", "Sentiment accelerating bullish — positive momentum building"
            elif vel < -0.02 and acc < 0:
                signal, desc = "MOMENTUM_SELL", "Sentiment accelerating bearish — negative momentum building"
            elif vel > 0.02 and acc < 0:
                signal, desc = "MOMENTUM_FADING_BULL", "Bullish momentum fading — sentiment still positive but slowing"
            elif vel < -0.02 and acc > 0:
                signal, desc = "MOMENTUM_FADING_BEAR", "Bearish momentum fading — sentiment still negative but recovering"
            else:
                signal, desc = "NEUTRAL", "No significant sentiment momentum"

            return {
                "current": round(current, 4), "velocity": round(vel, 4),
                "acceleration": round(acc, 4), "signal": signal, "description": desc,
            }
        except Exception as e:
            logger.error(f"Momentum calculation error: {e}")
            return {"current": 0.5, "velocity": 0, "acceleration": 0, "signal": "NEUTRAL", "description": "Error"}
