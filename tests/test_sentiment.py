"""Unit tests for sentiment analysis components."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest


class TestNarrativeDetector(unittest.TestCase):
    def setUp(self):
        from sentiment.narrative_detector import NarrativeDetector
        self.detector = NarrativeDetector()

    def test_detect_single_narrative(self):
        texts = ["Bitcoin ETF finally approved by SEC!"]
        results = self.detector.detect_narratives(texts)
        narratives = [n[0] for n in results]
        self.assertIn("ETF", narratives)
        self.assertIn("SEC", narratives)

    def test_detect_multiple_narratives(self):
        texts = [
            "Whale moves 10000 BTC off Binance",
            "DeFi yields are pumping with staking rewards",
            "SEC regulation concerns in India, RBI crypto ban discussion",
        ]
        results = self.detector.detect_narratives(texts)
        narratives = [n[0] for n in results]
        self.assertIn("whale", narratives)
        self.assertIn("DeFi", narratives)

    def test_detect_empty_text(self):
        results = self.detector.detect_narratives([])
        self.assertEqual(len(results), 0)

    def test_detect_no_match(self):
        results = self.detector.detect_narratives(["The weather is nice today"])
        self.assertEqual(len(results), 0)

    def test_narrative_summary(self):
        texts = ["ETF ETF ETF", "whale alert whale"]
        summary = self.detector.get_narrative_summary(texts)
        self.assertIsInstance(summary, list)
        if summary:
            self.assertIn("narrative", summary[0])
            self.assertIn("mentions", summary[0])
            self.assertIn("share_pct", summary[0])


class TestCoinPatternDetection(unittest.TestCase):
    def test_reddit_coin_detection(self):
        import re
        from config.coins import TRACKED_COINS

        patterns = {}
        for symbol, info in TRACKED_COINS.items():
            keywords = info["news_keywords"] + [symbol, info["name"]]
            pattern = re.compile(
                r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b",
                re.IGNORECASE,
            )
            patterns[symbol] = pattern

        text = "I'm buying more Bitcoin and ETH today because Solana is pumping"
        mentioned = [sym for sym, p in patterns.items() if p.search(text)]
        self.assertIn("BTC", mentioned)
        self.assertIn("ETH", mentioned)
        self.assertIn("SOL", mentioned)

    def test_no_false_positives(self):
        import re
        from config.coins import TRACKED_COINS

        patterns = {}
        for symbol, info in TRACKED_COINS.items():
            keywords = info["news_keywords"] + [symbol, info["name"]]
            pattern = re.compile(
                r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b",
                re.IGNORECASE,
            )
            patterns[symbol] = pattern

        text = "I made pasta for dinner tonight"
        mentioned = [sym for sym, p in patterns.items() if p.search(text)]
        self.assertEqual(len(mentioned), 0)


class TestFearGreedZones(unittest.TestCase):
    def test_zone_coverage(self):
        from config.constants import FEAR_GREED_ZONES
        for value in range(0, 100):
            found = False
            for (low, high), label in FEAR_GREED_ZONES.items():
                if low <= value < high:
                    found = True
                    break
            self.assertTrue(found, f"Value {value} not covered by any zone")


if __name__ == "__main__":
    unittest.main()
