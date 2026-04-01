"""Sentiment feature utilities — called by FeatureEngineer."""
import pandas as pd
from database.connection import get_engine
from loguru import logger


def get_sentiment_features(coin: str, hours: int = 4) -> pd.DataFrame:
    """Fetch aggregated sentiment features for a coin."""
    engine = get_engine()
    query = f"""
    SELECT window_start as timestamp, avg_sentiment, sentiment_std,
           bullish_count, bearish_count, neutral_count, fud_count,
           total_posts, sentiment_velocity, social_volume
    FROM sentiment_aggregated
    WHERE coin = '{coin}' AND window_size = '{hours}h'
    ORDER BY window_start ASC
    """
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        logger.error(f"Sentiment features error: {e}")
        return pd.DataFrame()
