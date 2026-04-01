"""Train all ML models after seeding historical data."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models.trainer import ModelTrainer
from database.connection import test_connection
from loguru import logger

def main():
    if not test_connection():
        logger.error("Database not available.")
        sys.exit(1)

    trainer = ModelTrainer()
    results = trainer.train_all_models()
    logger.success(f"Training complete: {len(results)} models trained")
    for r in results:
        logger.info(f"  {r}")

if __name__ == "__main__":
    main()
