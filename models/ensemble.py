import numpy as np
from loguru import logger
from models.xgboost_model import XGBoostModel
from models.prophet_model import ProphetModel
from models.lstm_model import LSTMModel


class EnsemblePredictor:
    def __init__(self, coin, horizon_hours=4):
        self.coin = coin
        self.horizon_hours = horizon_hours
        self.horizon_str = f"{horizon_hours}h"

        self.models = {
            "xgboost": XGBoostModel(coin, self.horizon_str),
            "prophet": ProphetModel(coin, horizon_hours),
            "lstm": LSTMModel(coin, self.horizon_str),
        }

        self.weights = {"xgboost": 0.45, "prophet": 0.30, "lstm": 0.25}

    def predict(self, features_df, current_price=None):
        predictions = {}

        for name, model in self.models.items():
            try:
                result = model.predict(current_price) if name == "prophet" else model.predict(features_df)
                if result:
                    predictions[name] = result
                    logger.info(f"{name}: {result['direction']} ({result['confidence']:.2%})")
            except Exception as e:
                logger.warning(f"Model {name} prediction failed: {e}")

        if not predictions:
            return None

        bull_score = 0
        bear_score = 0
        total_weight = 0

        for name, pred in predictions.items():
            weight = self.weights.get(name, 0.33)
            total_weight += weight

            if pred["direction"] == "UP":
                bull_score += weight * pred["confidence"]
            elif pred["direction"] == "DOWN":
                bear_score += weight * pred["confidence"]
            else:
                bull_score += weight * 0.5 * pred["confidence"]
                bear_score += weight * 0.5 * pred["confidence"]

        if total_weight > 0:
            bull_score /= total_weight
            bear_score /= total_weight

        if bull_score > bear_score + 0.05:
            direction, confidence = "UP", bull_score
        elif bear_score > bull_score + 0.05:
            direction, confidence = "DOWN", bear_score
        else:
            direction, confidence = "SIDEWAYS", 0.5

        directions = [p["direction"] for p in predictions.values()]
        full_agreement = len(set(directions)) == 1
        majority_agreement = directions.count(direction) >= 2

        if full_agreement:
            confidence = min(confidence * 1.2, 0.95)
        elif not majority_agreement:
            confidence *= 0.7

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "bull_score": round(bull_score, 4),
            "bear_score": round(bear_score, 4),
            "model_agreement": full_agreement,
            "majority_agreement": majority_agreement,
            "models_used": len(predictions),
            "individual_predictions": predictions,
            "model": "ensemble",
        }
