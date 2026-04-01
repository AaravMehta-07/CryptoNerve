import pandas as pd
import ta
from loguru import logger
from database.connection import get_engine


class TechnicalIndicators:
    def __init__(self):
        self.engine = get_engine()

    def calculate_all(self, df):
        """Calculate all technical indicators. df must have open, high, low, close, volume cols."""
        if len(df) < 50:
            logger.warning(f"Not enough data for indicators: {len(df)} rows")
            return df

        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

        macd = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_histogram"] = macd.macd_diff()

        bb = ta.volatility.BollingerBands(df["close"], window=20, window_dev=2)
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_middle"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_bandwidth"] = bb.bollinger_wband()

        df["atr"] = ta.volatility.AverageTrueRange(
            df["high"], df["low"], df["close"], window=14
        ).average_true_range()

        df["obv"] = ta.volume.OnBalanceVolumeIndicator(
            df["close"], df["volume"]
        ).on_balance_volume()

        df["ema_12"] = ta.trend.EMAIndicator(df["close"], window=12).ema_indicator()
        df["ema_26"] = ta.trend.EMAIndicator(df["close"], window=26).ema_indicator()
        df["sma_50"] = ta.trend.SMAIndicator(df["close"], window=50).sma_indicator()

        if len(df) >= 200:
            df["sma_200"] = ta.trend.SMAIndicator(df["close"], window=200).sma_indicator()

        df["volume_sma_20"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_20"]

        df["price_change_1h"] = df["close"].pct_change(periods=4)
        df["price_change_4h"] = df["close"].pct_change(periods=16)
        df["price_change_24h"] = df["close"].pct_change(periods=96)
        df["volatility_24h"] = df["close"].pct_change().rolling(window=96).std()

        return df

    def save_indicators(self, coin, df, interval="15m"):
        if df.empty:
            return

        indicator_cols = [
            "rsi", "macd", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_bandwidth",
            "atr", "obv", "ema_12", "ema_26", "sma_50",
            "volume_sma_20", "volume_ratio",
        ]

        records = []
        for _, row in df.iterrows():
            record = {
                "coin": coin,
                "timestamp": row.get("timestamp", row.name),
                "interval": interval,
            }
            for col in indicator_cols:
                record[col] = float(row[col]) if pd.notna(row.get(col)) else None

            record["sma_200"] = (
                float(row["sma_200"])
                if "sma_200" in row and pd.notna(row.get("sma_200"))
                else None
            )
            records.append(record)

        try:
            pd.DataFrame(records).to_sql(
                "technical_indicators", self.engine, if_exists="append", index=False
            )
        except Exception as e:
            logger.error(f"Error saving indicators: {e}")
