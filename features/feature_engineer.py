import pandas as pd
import numpy as np
from loguru import logger
from database.connection import get_engine
from features.technical_indicators import TechnicalIndicators


class FeatureEngineer:
    def __init__(self):
        self.engine = get_engine()
        self.ti = TechnicalIndicators()

    # ------------------------------------------------------------------
    # Core builder
    # ------------------------------------------------------------------
    def build_training_features(self, coin, interval="1h", days=90):
        """Build complete 25+ feature set for 1h direction prediction."""

        # 1. Price / OHLCV data (parameterized, MED-02)
        price_df = pd.read_sql(
            """SELECT timestamp, open, high, low, close, volume, quote_volume, num_trades
               FROM price_data
               WHERE coin = %(coin)s AND interval = %(interval)s
               AND timestamp > NOW() - (%(days)s || ' days')::INTERVAL
               ORDER BY timestamp ASC""",
            self.engine,
            params={"coin": coin, "interval": interval, "days": str(days)},
        )
        if price_df.empty or len(price_df) < 50:
            logger.warning(f"Insufficient price data for {coin}: {len(price_df)} rows")
            return None

        price_df.set_index("timestamp", inplace=True)

        # 2. Technical indicators (RSI, MACD, BB, ATR, OBV, EMA)
        price_df = self.ti.calculate_all(price_df)

        # 3. Extra technical features
        price_df = self._add_technical_extras(price_df)

        # 4. Temporal / cyclical features (hour of day, day of week)
        price_df = self._add_temporal_features(price_df)

        # 5. Lag / autoregressive features
        price_df = self._add_lag_features(price_df)

        # 6. Rolling statistical features
        price_df = self._add_rolling_features(price_df)

        # 7. Sentiment features (1h windows)
        price_df = self._merge_sentiment(price_df, coin, interval)

        # 8. On-chain features
        price_df = self._merge_onchain(price_df, coin, interval)

        # 9. BTC correlation for altcoins
        if coin != "BTC":
            price_df = self._add_btc_correlation(price_df, interval, days)

        # 10. Target: next 1h candle direction (HIGH-01 FIX: drop NaN BEFORE fill)
        price_df["target_1h"] = (price_df["close"].pct_change().shift(-1) > 0).astype(int)
        price_df["target_1h_pct"] = price_df["close"].pct_change().shift(-1)

        # DROP NaN targets before any fill — prevents label corruption
        price_df = price_df.dropna(subset=["target_1h", "target_1h_pct"])
        price_df = price_df.ffill().fillna(0)
        price_df = price_df.replace([np.inf, -np.inf], 0)

        logger.info(f"Built feature set for {coin} ({interval}): {price_df.shape}")
        return price_df

    # ------------------------------------------------------------------
    # Feature helpers
    # ------------------------------------------------------------------
    def _add_technical_extras(self, df):
        """Additional technical indicators beyond base set."""
        # RSI(7) — faster RSI for short-term signals
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        df["rsi_7"] = 100 - (100 / (1 + gain.rolling(7).mean() / (loss.rolling(7).mean() + 1e-9)))

        # Bollinger %B — where price sits within bands
        if "bb_upper" in df.columns and "bb_lower" in df.columns:
            band_width = df["bb_upper"] - df["bb_lower"] + 1e-9
            df["bb_pct_b"] = (df["close"] - df["bb_lower"]) / band_width

        # MACD histogram slope (acceleration)
        if "macd_histogram" in df.columns:
            df["macd_hist_slope"] = df["macd_histogram"].diff()

        # ATR ratio: short volatility vs long volatility (compression detector)
        atr_6 = self._true_range(df).rolling(6).mean()
        atr_24 = self._true_range(df).rolling(24).mean()
        df["atr_ratio"] = atr_6 / (atr_24 + 1e-9)

        # Volume ratio: current volume vs 20-period SMA
        df["volume_ratio"] = df["volume"] / (df["volume"].rolling(20).mean() + 1e-9)

        # Volume spike: z-score of current volume
        vol_mean = df["volume"].rolling(24).mean()
        vol_std = df["volume"].rolling(24).std()
        df["volume_zscore"] = (df["volume"] - vol_mean) / (vol_std + 1e-9)

        # OBV slope
        if "obv" in df.columns:
            df["obv_slope"] = df["obv"].diff(3) / (df["obv"].abs().rolling(3).mean() + 1e-9)

        # Price momentum (vs 6h and 24h ago)
        df["price_mom_6h"] = df["close"].pct_change(6)
        df["price_mom_24h"] = df["close"].pct_change(24)

        # High-low range as % of close (intra-candle range)
        df["hl_range_pct"] = (df["high"] - df["low"]) / (df["close"] + 1e-9)

        return df

    def _true_range(self, df):
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift()).abs()
        lc = (df["low"] - df["close"].shift()).abs()
        return pd.concat([hl, hc, lc], axis=1).max(axis=1)

    def _add_temporal_features(self, df):
        """Cyclical encoding of hour and day — captures intraday/weekly patterns."""
        idx = df.index
        if hasattr(idx, "hour"):
            hour = idx.hour
            dow = idx.dayofweek
        else:
            dt = pd.to_datetime(idx)
            hour = dt.hour
            dow = dt.dayofweek

        # Cyclical sin/cos encoding (avoids discontinuity at 23→0 and 6→0)
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        df["is_weekend"] = (dow >= 5).astype(int)

        return df

    def _add_lag_features(self, df):
        """Autoregressive: previous candle closes and directions."""
        for lag in [1, 2, 3, 6, 12, 24]:
            df[f"close_lag_{lag}"] = df["close"].shift(lag)
            df[f"return_lag_{lag}"] = df["close"].pct_change().shift(lag)

        # Previous 3 candle directions (binary: 1=up, 0=down)
        ret = df["close"].pct_change()
        for lag in [1, 2, 3]:
            df[f"dir_lag_{lag}"] = (ret.shift(lag) > 0).astype(int)

        return df

    def _add_rolling_features(self, df):
        """Rolling statistical moments for volatility regime detection."""
        returns = df["close"].pct_change()
        for window in [6, 12, 24]:
            df[f"vol_{window}h"] = returns.rolling(window).std()
            df[f"mean_ret_{window}h"] = returns.rolling(window).mean()

        # Skewness and kurtosis of 24h returns
        df["skew_24h"] = returns.rolling(24).skew()
        df["kurt_24h"] = returns.rolling(24).kurt()

        return df

    def _merge_sentiment(self, price_df, coin, interval):
        """Merge 1h sentiment aggregates as features."""
        try:
            sent_df = pd.read_sql(
                """SELECT window_start as timestamp, avg_sentiment, sentiment_std,
                          bullish_count, bearish_count, neutral_count, fud_count,
                          total_posts, sentiment_velocity, social_volume
                   FROM sentiment_aggregated
                   WHERE coin = %(coin)s AND window_size = '1h'
                   ORDER BY window_start ASC""",
                self.engine, params={"coin": coin},
            )
            if not sent_df.empty:
                sent_df.set_index("timestamp", inplace=True)
                sent_df = sent_df.resample(interval).ffill()
                price_df = price_df.join(sent_df, how="left")
                sent_cols = sent_df.columns.tolist()
                price_df[sent_cols] = price_df[sent_cols].ffill()
        except Exception as e:
            logger.warning(f"Sentiment merge failed for {coin}: {e}")
        return price_df

    def _merge_onchain(self, price_df, coin, interval):
        """Merge 4h on-chain metrics as features."""
        try:
            onchain_df = pd.read_sql(
                """SELECT timestamp, whale_tx_count, whale_volume_usd,
                          exchange_inflow_usd, exchange_outflow_usd,
                          net_flow_usd, whale_activity_score
                   FROM onchain_metrics
                   WHERE coin = %(coin)s AND window_size = '4h'
                   ORDER BY timestamp ASC""",
                self.engine, params={"coin": coin},
            )
            if not onchain_df.empty:
                onchain_df.set_index("timestamp", inplace=True)
                onchain_df = onchain_df.resample(interval).ffill()
                price_df = price_df.join(onchain_df, how="left", rsuffix="_oc")
                oc_cols = onchain_df.columns.tolist()
                price_df[oc_cols] = price_df[oc_cols].ffill()
        except Exception as e:
            logger.warning(f"On-chain merge failed for {coin}: {e}")
        return price_df

    def _add_btc_correlation(self, price_df, interval, days):
        """Add BTC 6h rolling correlation and price momentum for altcoins."""
        try:
            btc_df = pd.read_sql(
                """SELECT timestamp, close
                   FROM price_data
                   WHERE coin = 'BTC' AND interval = %(interval)s
                   AND timestamp > NOW() - (%(days)s || ' days')::INTERVAL
                   ORDER BY timestamp ASC""",
                self.engine,
                params={"interval": interval, "days": str(days)},
            )
            if not btc_df.empty:
                btc_df.set_index("timestamp", inplace=True)
                btc_ret = btc_df["close"].pct_change().rename("btc_return")
                btc_mom_6 = btc_df["close"].pct_change(6).rename("btc_mom_6h")
                price_df = price_df.join(btc_ret, how="left")
                price_df = price_df.join(btc_mom_6, how="left")
                # Rolling 12h correlation between coin and BTC returns
                coin_ret = price_df["close"].pct_change()
                price_df["btc_corr_12h"] = coin_ret.rolling(12).corr(
                    price_df["btc_return"].fillna(0)
                )
        except Exception as e:
            logger.warning(f"BTC correlation merge failed: {e}")
        return price_df

    # ------------------------------------------------------------------
    # Feature column list (for model input)
    # ------------------------------------------------------------------
    def get_feature_columns(self):
        return [
            # Base OHLCV
            "open", "high", "low", "close", "volume", "quote_volume", "num_trades",
            # Technical
            "rsi", "rsi_7",
            "macd", "macd_signal", "macd_histogram", "macd_hist_slope",
            "bb_upper", "bb_middle", "bb_lower", "bb_bandwidth", "bb_pct_b",
            "atr", "atr_ratio",
            "obv", "obv_slope",
            "ema_12", "ema_26",
            "volume_ratio", "volume_zscore",
            "price_mom_6h", "price_mom_24h",
            "hl_range_pct",
            # Temporal
            "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend",
            # Lag / autoregressive
            "return_lag_1", "return_lag_2", "return_lag_3",
            "return_lag_6", "return_lag_12", "return_lag_24",
            "dir_lag_1", "dir_lag_2", "dir_lag_3",
            # Rolling stats
            "vol_6h", "vol_12h", "vol_24h",
            "mean_ret_6h", "mean_ret_12h", "mean_ret_24h",
            "skew_24h", "kurt_24h",
            # Sentiment
            "avg_sentiment", "sentiment_std", "sentiment_velocity",
            "bullish_count", "bearish_count", "neutral_count", "fud_count",
            "total_posts", "social_volume",
            # On-chain
            "whale_tx_count", "whale_volume_usd",
            "exchange_inflow_usd", "exchange_outflow_usd",
            "net_flow_usd", "whale_activity_score",
            # BTC cross-asset (for alts)
            "btc_return", "btc_mom_6h", "btc_corr_12h",
        ]

    # ------------------------------------------------------------------
    # Live prediction feature builder (last N candles from DB)
    # ------------------------------------------------------------------
    def build_prediction_features(self, coin, interval="1h", lookback_hours=48):
        """Build features for the most recent candles — used at prediction time."""
        return self.build_training_features(coin, interval=interval, days=lookback_hours // 24 + 1)
