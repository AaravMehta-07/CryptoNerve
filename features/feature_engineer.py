import pandas as pd
import numpy as np
from loguru import logger
from database.connection import get_engine
from features.technical_indicators import TechnicalIndicators


class FeatureEngineer:
    def __init__(self):
        self.engine = get_engine()
        self.ti = TechnicalIndicators()

    def build_training_features(self, coin, interval="15m", days=90):
        """Build complete ML feature set for a coin."""
        price_query = f"""
        SELECT timestamp, open, high, low, close, volume, quote_volume, num_trades
        FROM price_data
        WHERE coin = '{coin}' AND interval = '{interval}'
        AND timestamp > NOW() - INTERVAL '{days} days'
        ORDER BY timestamp ASC
        """
        price_df = pd.read_sql(price_query, self.engine)
        if price_df.empty or len(price_df) < 100:
            logger.warning(f"Insufficient price data for {coin}: {len(price_df)} rows")
            return None

        price_df.set_index("timestamp", inplace=True)
        price_df = self.ti.calculate_all(price_df)

        # Merge sentiment features
        sentiment_query = f"""
        SELECT window_start as timestamp, avg_sentiment, sentiment_std,
               bullish_count, bearish_count, neutral_count, fud_count,
               total_posts, sentiment_velocity, social_volume
        FROM sentiment_aggregated
        WHERE coin = '{coin}' AND window_size = '1h'
        ORDER BY window_start ASC
        """
        sentiment_df = pd.read_sql(sentiment_query, self.engine)
        if not sentiment_df.empty:
            sentiment_df.set_index("timestamp", inplace=True)
            sentiment_df = sentiment_df.resample("15min").ffill()
            price_df = price_df.join(sentiment_df, how="left")
            price_df[sentiment_df.columns] = price_df[sentiment_df.columns].ffill()

        # Merge on-chain features
        onchain_query = f"""
        SELECT timestamp, whale_tx_count, whale_volume_usd,
               exchange_inflow_usd, exchange_outflow_usd, net_flow_usd,
               whale_activity_score
        FROM onchain_metrics
        WHERE coin = '{coin}' AND window_size = '4h'
        ORDER BY timestamp ASC
        """
        onchain_df = pd.read_sql(onchain_query, self.engine)
        if not onchain_df.empty:
            onchain_df.set_index("timestamp", inplace=True)
            onchain_df = onchain_df.resample("15min").ffill()
            price_df = price_df.join(onchain_df, how="left", rsuffix="_onchain")
            price_df[onchain_df.columns] = price_df[onchain_df.columns].ffill()

        # Create target variables
        for horizon_name, periods in [("target_1h", 4), ("target_4h", 16), ("target_24h", 96)]:
            future_return = price_df["close"].pct_change(periods=periods).shift(-periods)
            price_df[horizon_name] = (future_return > 0).astype(int)
            price_df[f"{horizon_name}_pct"] = future_return

        price_df = price_df.ffill().fillna(0)
        price_df = price_df.dropna(subset=["target_1h"])
        price_df = price_df.replace([np.inf, -np.inf], 0)

        logger.info(f"Built feature set for {coin}: {price_df.shape}")
        return price_df

    def get_feature_columns(self):
        return [
            "open", "high", "low", "close", "volume", "quote_volume", "num_trades",
            "rsi", "macd", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_bandwidth",
            "atr", "obv", "ema_12", "ema_26",
            "volume_sma_20", "volume_ratio",
            "price_change_1h", "price_change_4h", "price_change_24h",
            "volatility_24h",
            "avg_sentiment", "sentiment_std",
            "bullish_count", "bearish_count", "neutral_count", "fud_count",
            "total_posts", "sentiment_velocity", "social_volume",
            "whale_tx_count", "whale_volume_usd",
            "exchange_inflow_usd", "exchange_outflow_usd", "net_flow_usd",
            "whale_activity_score",
        ]
