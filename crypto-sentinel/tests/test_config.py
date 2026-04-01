"""Unit tests for config layer."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest


class TestSettings(unittest.TestCase):
    def test_settings_import(self):
        from config.settings import settings
        self.assertIsNotNone(settings)

    def test_database_url(self):
        from config.settings import settings
        url = settings.DATABASE_URL
        self.assertIn("sqlite:///", url)
        self.assertIn("crypto_sentinel.db", url)


class TestConstants(unittest.TestCase):
    def test_sentiment_labels(self):
        from config.constants import SENTIMENT_LABELS, BULLISH, BEARISH, NEUTRAL, FUD
        self.assertIn(BULLISH, SENTIMENT_LABELS)
        self.assertIn(BEARISH, SENTIMENT_LABELS)
        self.assertIn(NEUTRAL, SENTIMENT_LABELS)
        self.assertIn(FUD, SENTIMENT_LABELS)

    def test_signal_types(self):
        from config.constants import BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL
        self.assertEqual(BUY, "BUY")
        self.assertEqual(SELL, "SELL")
        self.assertEqual(HOLD, "HOLD")

    def test_thresholds(self):
        from config.constants import WHALE_ALERT_THRESHOLD_USD, MIN_SIGNAL_CONFIDENCE
        self.assertEqual(WHALE_ALERT_THRESHOLD_USD, 1_000_000)
        self.assertGreater(MIN_SIGNAL_CONFIDENCE, 0)
        self.assertLess(MIN_SIGNAL_CONFIDENCE, 1)


class TestCoins(unittest.TestCase):
    def test_tracked_coins(self):
        from config.coins import TRACKED_COINS
        self.assertIn("BTC", TRACKED_COINS)
        self.assertIn("ETH", TRACKED_COINS)
        self.assertIn("SOL", TRACKED_COINS)

    def test_coin_structure(self):
        from config.coins import TRACKED_COINS
        for symbol, info in TRACKED_COINS.items():
            self.assertIn("symbol", info)
            self.assertIn("name", info)
            self.assertIn("binance_symbol", info)
            self.assertIn("subreddits", info)
            self.assertIn("news_keywords", info)
            self.assertIn("color", info)
            self.assertIsInstance(info["subreddits"], list)
            self.assertIsInstance(info["news_keywords"], list)


if __name__ == "__main__":
    unittest.main()
