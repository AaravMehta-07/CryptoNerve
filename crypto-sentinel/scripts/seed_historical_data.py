"""Seed historical price and indicator data. Run once before starting the full pipeline."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ingestion.price_collector import PriceCollector
from features.technical_indicators import TechnicalIndicators
from database.connection import test_connection, get_engine
from config.coins import TRACKED_COINS
from loguru import logger
import pandas as pd

def main():
    if not test_connection():
        logger.error("Database not available. Check data/ directory permissions.")
        sys.exit(1)

    collector = PriceCollector()
    ti = TechnicalIndicators()
    engine = get_engine()

    for symbol, info in TRACKED_COINS.items():
        logger.info(f"Seeding {symbol}...")
        for interval in ["15m", "1h", "4h"]:
            records = collector.fetch_historical_data(info["binance_symbol"], interval=interval, days=90)
            collector.save_prices(symbol, records, interval)

        price_df = pd.read_sql(f"""
            SELECT timestamp, open, high, low, close, volume
            FROM price_data WHERE coin = '{symbol}' AND interval = '15m'
            ORDER BY timestamp ASC
        """, engine)

        if not price_df.empty:
            price_df.set_index("timestamp", inplace=True)
            price_df = ti.calculate_all(price_df)
            ti.save_indicators(symbol, price_df, "15m")
            logger.success(f"✅ {symbol} seeded: {len(price_df)} candles + indicators")

    logger.success("Historical data seeding complete!")

if __name__ == "__main__":
    main()
