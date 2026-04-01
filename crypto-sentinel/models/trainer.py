from loguru import logger
from features.feature_engineer import FeatureEngineer
from models.xgboost_model import XGBoostModel
from models.prophet_model import ProphetModel
from models.lstm_model import LSTMModel
from config.coins import TRACKED_COINS
from database.connection import get_engine
import pandas as pd
from datetime import date


class ModelTrainer:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.engine = get_engine()

    def train_all_models(self):
        results = []

        for coin in TRACKED_COINS.keys():
            logger.info(f"Training models for {coin}...")
            df = self.feature_engineer.build_training_features(coin, interval="15m", days=90)
            if df is None or len(df) < 200:
                logger.warning(f"Insufficient data for {coin}, skipping")
                continue

            feature_cols = self.feature_engineer.get_feature_columns()
            available_features = [c for c in feature_cols if c in df.columns]

            for horizon_name, horizon_hours in [("target_1h", 1), ("target_4h", 4), ("target_24h", 24)]:
                if horizon_name not in df.columns:
                    continue

                logger.info(f"Training {coin} - {horizon_hours}h horizon...")

                # XGBoost
                try:
                    xgb_model = XGBoostModel(coin, f"{horizon_hours}h")
                    xgb_metrics = xgb_model.train(df, available_features, horizon_name)
                    results.append(xgb_metrics)
                    self._save_performance(xgb_metrics, coin, horizon_hours)
                except Exception as e:
                    logger.error(f"XGBoost training failed for {coin}: {e}")

                # Prophet
                try:
                    prophet_model = ProphetModel(coin, horizon_hours)
                    prophet_metrics = prophet_model.train(df)
                    results.append(prophet_metrics)
                except Exception as e:
                    logger.error(f"Prophet training failed for {coin}: {e}")

                # LSTM
                try:
                    lstm_model = LSTMModel(coin, f"{horizon_hours}h")
                    lstm_metrics = lstm_model.train(df, available_features, horizon_name)
                    if lstm_metrics:
                        results.append(lstm_metrics)
                        self._save_performance(lstm_metrics, coin, horizon_hours)
                except Exception as e:
                    logger.error(f"LSTM training failed for {coin}: {e}")

        logger.info(f"Training complete. {len(results)} models trained.")
        return results

    def _save_performance(self, metrics, coin, horizon_hours):
        try:
            record = {
                "model_name": metrics["model"],
                "coin": coin,
                "horizon_hours": horizon_hours,
                "evaluation_date": date.today(),
                "accuracy": metrics.get("cv_accuracy_mean", metrics.get("val_accuracy", 0)),
                "total_predictions": 0,
                "correct_predictions": 0,
            }
            pd.DataFrame([record]).to_sql(
                "model_performance", self.engine, if_exists="append", index=False
            )
        except Exception:
            pass
