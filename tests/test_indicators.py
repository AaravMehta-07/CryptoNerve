"""Unit tests for technical indicators calculation."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class TestTechnicalIndicators(unittest.TestCase):
    def setUp(self):
        from features.technical_indicators import TechnicalIndicators
        self.ti = TechnicalIndicators.__new__(TechnicalIndicators)

        # Generate 250 synthetic candles
        np.random.seed(42)
        dates = [datetime(2024, 1, 1) + timedelta(minutes=15 * i) for i in range(250)]
        base_price = 50000
        prices = [base_price]
        for i in range(249):
            change = np.random.randn() * 0.005
            prices.append(prices[-1] * (1 + change))

        self.df = pd.DataFrame({
            "open": [p * (1 + np.random.uniform(-0.002, 0.002)) for p in prices],
            "high": [p * (1 + np.random.uniform(0, 0.01)) for p in prices],
            "low": [p * (1 - np.random.uniform(0, 0.01)) for p in prices],
            "close": prices,
            "volume": [np.random.uniform(100, 1000) for _ in range(250)],
        }, index=dates)

    def test_calculate_all_returns_dataframe(self):
        result = self.ti.calculate_all(self.df)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)

    def test_rsi_column_exists(self):
        result = self.ti.calculate_all(self.df)
        self.assertIn("rsi", result.columns)

    def test_rsi_range(self):
        result = self.ti.calculate_all(self.df)
        rsi_valid = result["rsi"].dropna()
        self.assertTrue((rsi_valid >= 0).all() and (rsi_valid <= 100).all())

    def test_macd_columns(self):
        result = self.ti.calculate_all(self.df)
        for col in ["macd", "macd_signal", "macd_histogram"]:
            self.assertIn(col, result.columns)

    def test_bollinger_bands(self):
        result = self.ti.calculate_all(self.df)
        for col in ["bb_upper", "bb_middle", "bb_lower", "bb_bandwidth"]:
            self.assertIn(col, result.columns)

        valid = result.dropna(subset=["bb_upper", "bb_middle", "bb_lower"])
        if not valid.empty:
            self.assertTrue((valid["bb_upper"] >= valid["bb_middle"]).all())
            self.assertTrue((valid["bb_middle"] >= valid["bb_lower"]).all())

    def test_ema_columns(self):
        result = self.ti.calculate_all(self.df)
        self.assertIn("ema_12", result.columns)
        self.assertIn("ema_26", result.columns)

    def test_volume_ratio(self):
        result = self.ti.calculate_all(self.df)
        self.assertIn("volume_ratio", result.columns)
        self.assertIn("volume_sma_20", result.columns)

    def test_insufficient_data(self):
        small_df = self.df.head(10)
        result = self.ti.calculate_all(small_df)
        self.assertEqual(len(result), len(small_df))

    def test_sma_200(self):
        result = self.ti.calculate_all(self.df)
        self.assertIn("sma_200", result.columns)


if __name__ == "__main__":
    unittest.main()
