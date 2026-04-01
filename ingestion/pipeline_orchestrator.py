"""
Pipeline Orchestrator — staggered cycles with hardware-aware throttling.

Scheduling design (i5-8300H + GTX 1650):
  - Price tick     : every 60s   (lightweight, no CPU spike)
  - News/RSS       : every 15min (network I/O only, no CPU)
  - On-chain       : every 10min (network I/O only)
  - Sentiment/LLM  : every 20min (CPU-heavy — staggered from news)
  - Signal gen     : every 10min (lightweight math)
  - Retrain        : every 6h    (very heavy — runs during low-load window)

Hardware guards:
  - CPU load checked before every LLM batch (via psutil)
  - Retrain skipped if CPU > THROTTLE_CPU_PCT at schedule time
  - All heavy ops log a throttle warning if CPU > 80%
"""

import time
import schedule
import psutil
from loguru import logger
from ingestion.reddit_collector import RedditCollector   # no-op stub
from ingestion.news_collector import NewsCollector
from ingestion.price_collector import PriceCollector
from ingestion.onchain_collector import OnchainCollector
from sentiment.sentiment_engine import SentimentEngine
from features.technical_indicators import TechnicalIndicators
from features.feature_engineer import FeatureEngineer
from models.trainer import ModelTrainer
from models.accuracy_tracker import AccuracyTracker
from signals.signal_generator import SignalGenerator
from signals.fear_greed_index import FearGreedIndex
from config.settings import settings
from config.coins import TRACKED_COINS
from database.connection import test_connection, get_engine
import pandas as pd

# CPU percentage above which heavy workloads are deferred
THROTTLE_CPU_PCT   = 85   # defer LLM / retrain above this
WARN_CPU_PCT       = 70   # log a warning above this
CPU_POLL_INTERVAL  = 1.0  # seconds for psutil measurement window


def _cpu_percent() -> float:
    """1-second blocking CPU measurement (more accurate than instant)."""
    return psutil.cpu_percent(interval=CPU_POLL_INTERVAL)


def _wait_for_headroom(label: str, threshold: float = THROTTLE_CPU_PCT, timeout: int = 120):
    """Block until CPU drops below threshold, or timeout seconds pass."""
    waited = 0
    while waited < timeout:
        cpu = _cpu_percent()
        if cpu < threshold:
            return True
        logger.warning(f"[throttle] {label}: CPU at {cpu:.0f}% — waiting for headroom…")
        time.sleep(5)
        waited += 5
    logger.warning(f"[throttle] {label}: timeout after {timeout}s — proceeding anyway")
    return False


class PipelineOrchestrator:
    def __init__(self):
        logger.info("Initializing Pipeline Orchestrator…")
        self.reddit   = RedditCollector()   # no-op stub
        self.news     = NewsCollector()
        self.prices   = PriceCollector()
        self.onchain  = OnchainCollector()
        self.sentiment = SentimentEngine()
        self.ti       = TechnicalIndicators()
        self.trainer  = ModelTrainer()
        self.accuracy_tracker = AccuracyTracker()
        self.signal_generator = SignalGenerator()
        self.fear_greed = FearGreedIndex()
        self.engine   = get_engine()

    # -----------------------------------------------------------------------
    # One-time startup tasks
    # -----------------------------------------------------------------------
    def seed_historical_data(self):
        logger.info("Seeding historical price data (3 months)…")
        for symbol, info in TRACKED_COINS.items():
            logger.info(f"  Fetching {symbol}…")
            for interval in ["15m", "1h", "4h"]:
                records = self.prices.fetch_historical_data(
                    info["binance_symbol"], interval=interval, days=90
                )
                self.prices.save_prices(symbol, records, interval)

            # Calculate technical indicators for 15m baseline
            df = pd.read_sql(
                f"SELECT timestamp, open, high, low, close, volume "
                f"FROM price_data WHERE coin='{symbol}' AND interval='15m' "
                f"ORDER BY timestamp ASC",
                self.engine,
            )
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df = self.ti.calculate_all(df)
                self.ti.save_indicators(symbol, df, "15m")

        logger.info("Historical data seeding complete")

    def initial_training(self):
        logger.info("Training initial models (this takes ~60-80 min on your hardware)…")
        _wait_for_headroom("initial_training", threshold=60, timeout=300)
        results = self.trainer.train_all_models()
        logger.info(f"Initial training complete: {len(results)} models trained")

    # -----------------------------------------------------------------------
    # Recurring cycles
    # -----------------------------------------------------------------------
    def price_cycle(self):
        """Every 60s — lightweight, no throttle needed."""
        try:
            self.prices.run()
        except Exception as e:
            logger.error(f"Price cycle error: {e}")

    def news_cycle(self):
        """Every 15min — network I/O only, not CPU intensive."""
        try:
            self.news.run()
            logger.info("News collection cycle complete")
        except Exception as e:
            logger.error(f"News cycle error: {e}")

    def onchain_cycle(self):
        """Every 10min — network I/O only."""
        try:
            self.onchain.run()
            logger.info("On-chain collection cycle complete")
        except Exception as e:
            logger.error(f"On-chain cycle error: {e}")

    def sentiment_cycle(self):
        """
        Every 20min — CPU-heavy (Mistral 7B inference).
        Guarded: skips if CPU is already slammed, waits up to 2min for headroom.
        """
        cpu = _cpu_percent()
        if cpu > THROTTLE_CPU_PCT:
            logger.warning(
                f"[throttle] Sentiment cycle deferred — CPU at {cpu:.0f}% "
                f"(threshold {THROTTLE_CPU_PCT}%) — will retry next scheduled run"
            )
            return
        if cpu > WARN_CPU_PCT:
            logger.warning(f"[throttle] Sentiment cycle starting at high CPU: {cpu:.0f}%")

        try:
            self.sentiment.run()
            logger.info("Sentiment cycle complete")
        except Exception as e:
            logger.error(f"Sentiment cycle error: {e}")

    def signal_cycle(self):
        """Every 10min — lightweight math + DB reads."""
        try:
            signals = self.signal_generator.generate_all_signals()
            fg      = self.fear_greed.calculate()
            self.accuracy_tracker.update_prediction_outcomes()
            logger.info(f"Signal cycle: {len(signals)} signals | F&G: {fg['index_value']}")
        except Exception as e:
            logger.error(f"Signal cycle error: {e}")

    def retrain_cycle(self):
        """
        Every 6h — very heavy (AutoGluon + XGB + LSTM).
        Will wait up to 5min for CPU to drop below threshold before starting.
        If CPU stays high, skips this cycle entirely.
        """
        cpu = _cpu_percent()
        if cpu > THROTTLE_CPU_PCT:
            logger.warning(
                f"[throttle] Retrain deferred — CPU at {cpu:.0f}% — "
                f"waiting up to 5min for headroom…"
            )
            has_headroom = _wait_for_headroom("retrain_cycle", threshold=THROTTLE_CPU_PCT, timeout=300)
            if not has_headroom:
                logger.warning("[throttle] Retrain skipped this cycle — CPU remained high")
                return

        try:
            logger.info("Starting scheduled model retrain…")
            self.trainer.train_all_models()
            logger.info("Scheduled retrain complete")
        except Exception as e:
            logger.error(f"Retrain cycle error: {e}")

    # -----------------------------------------------------------------------
    # Main run loop
    # -----------------------------------------------------------------------
    def run(self):
        logger.info("=" * 60)
        logger.info("CRYPTO SENTINEL PIPELINE STARTING")
        logger.info(f"  CPU throttle threshold : {THROTTLE_CPU_PCT}%")
        logger.info(f"  CPU warning threshold  : {WARN_CPU_PCT}%")
        logger.info("=" * 60)

        if not test_connection():
            logger.error("Database connection failed. Exiting.")
            return

        # Seed + initial train if DB is empty
        check_query = "SELECT COUNT(*) as cnt FROM price_data"
        try:
            result = pd.read_sql(check_query, self.engine)
            needs_seed = int(result.iloc[0]["cnt"]) < 1000
        except Exception:
            needs_seed = True

        if needs_seed:
            self.seed_historical_data()
            self.initial_training()

        # ── Staggered schedule to avoid simultaneous CPU spikes ────────────
        #  :00  price (60s)
        #  :10  price + signal
        #  :15  news  (30min stagger from signal)
        #  :20  sentiment (20min after news — data needs to land first)
        #  :25  on-chain
        #  ...  retrain every 6h
        schedule.every(1).minutes.do(self.price_cycle)
        schedule.every(15).minutes.do(self.news_cycle)
        schedule.every(10).minutes.do(self.onchain_cycle)
        schedule.every(20).minutes.do(self.sentiment_cycle)
        schedule.every(10).minutes.do(self.signal_cycle)
        schedule.every(6).hours.do(self.retrain_cycle)

        # Run initial lightweight cycles (skip sentiment/retrain at startup
        # to avoid hammering the system immediately)
        logger.info("Running initial data collection…")
        self.price_cycle()
        self.news_cycle()
        self.onchain_cycle()
        self.signal_cycle()

        # Delay first sentiment run by 3min to let news land in DB
        logger.info("First sentiment cycle queued in 3 min (waiting for news to land)…")
        schedule.every(3).minutes.do(self.sentiment_cycle).run_once = True

        logger.info("Pipeline running. Press Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(10)


if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    orchestrator.run()
