import time
import schedule
from loguru import logger
from ingestion.reddit_collector import RedditCollector
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


class PipelineOrchestrator:
    def __init__(self):
        logger.info("Initializing Pipeline Orchestrator...")
        self.reddit = RedditCollector()
        self.news = NewsCollector()
        self.prices = PriceCollector()
        self.onchain = OnchainCollector()
        self.sentiment = SentimentEngine()
        self.ti = TechnicalIndicators()
        self.trainer = ModelTrainer()
        self.accuracy_tracker = AccuracyTracker()
        self.signal_generator = SignalGenerator()
        self.fear_greed = FearGreedIndex()
        self.engine = get_engine()

    def seed_historical_data(self):
        logger.info("Seeding historical price data (3 months)...")
        for symbol, info in TRACKED_COINS.items():
            logger.info(f"Fetching historical data for {symbol}...")
            records = self.prices.fetch_historical_data(
                info["binance_symbol"], interval="15m", days=90
            )
            self.prices.save_prices(symbol, records, "15m")

            for interval in ["1h", "4h"]:
                records = self.prices.fetch_historical_data(
                    info["binance_symbol"], interval=interval, days=90
                )
                self.prices.save_prices(symbol, records, interval)

            price_query = f"""
            SELECT timestamp, open, high, low, close, volume
            FROM price_data
            WHERE coin = '{symbol}' AND interval = '15m'
            ORDER BY timestamp ASC
            """
            df = pd.read_sql(price_query, self.engine)
            if not df.empty:
                df.set_index("timestamp", inplace=True)
                df = self.ti.calculate_all(df)
                self.ti.save_indicators(symbol, df, "15m")

        logger.info("Historical data seeding complete")

    def initial_training(self):
        logger.info("Training initial models...")
        results = self.trainer.train_all_models()
        logger.info(f"Initial training complete: {len(results)} models trained")

    def data_collection_cycle(self):
        try:
            self.reddit.run()
            self.news.run()
            self.prices.run()
            self.onchain.run()
            logger.info("Data collection cycle complete")
        except Exception as e:
            logger.error(f"Data collection error: {e}")

    def sentiment_cycle(self):
        try:
            self.sentiment.run()
            logger.info("Sentiment cycle complete")
        except Exception as e:
            logger.error(f"Sentiment cycle error: {e}")

    def signal_cycle(self):
        try:
            signals = self.signal_generator.generate_all_signals()
            fg = self.fear_greed.calculate()
            self.accuracy_tracker.update_prediction_outcomes()
            logger.info(f"Signal cycle: {len(signals)} signals, F&G: {fg['index_value']}")
        except Exception as e:
            logger.error(f"Signal cycle error: {e}")

    def retrain_cycle(self):
        try:
            self.trainer.train_all_models()
            logger.info("Model retrain cycle complete")
        except Exception as e:
            logger.error(f"Retrain cycle error: {e}")

    def run(self):
        logger.info("=" * 60)
        logger.info("CRYPTO SENTINEL PIPELINE STARTING")
        logger.info("=" * 60)

        if not test_connection():
            logger.error("Database connection failed. Exiting.")
            return

        # Check if we need to seed data
        check_query = "SELECT COUNT(*) as cnt FROM price_data"
        try:
            result = pd.read_sql(check_query, self.engine)
            if result.iloc[0]["cnt"] < 1000:
                self.seed_historical_data()
                self.initial_training()
        except Exception:
            self.seed_historical_data()
            self.initial_training()

        # Schedule recurring jobs
        schedule.every(5).minutes.do(self.data_collection_cycle)
        schedule.every(3).minutes.do(self.sentiment_cycle)
        schedule.every(5).minutes.do(self.signal_cycle)
        schedule.every(1).hours.do(self.retrain_cycle)

        # Run initial cycles
        self.data_collection_cycle()
        self.sentiment_cycle()
        self.signal_cycle()

        logger.info("Pipeline running. Press Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(10)


if __name__ == "__main__":
    orchestrator = PipelineOrchestrator()
    orchestrator.run()
