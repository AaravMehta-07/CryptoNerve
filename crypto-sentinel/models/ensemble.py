"""
Ensemble predictor: AutoGluon (0.45) + LSTM (0.30) + XGBoost (0.25) by default.
- Per-coin optimal weights learned via scipy.optimize on validation data
- Agreement filter: signals only on 2/3 model consensus
- Confidence gating: MIN_SIGNAL_CONFIDENCE threshold
- Walk-forward weight calibration
"""
import numpy as np
import json
import os
from loguru import logger
from models.xgboost_model import XGBoostModel
from models.lstm_model import LSTMModel
from models.autogluon_model import AutoGluonModel
from config.settings import settings
from config.constants import MIN_SIGNAL_CONFIDENCE

try:
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not installed — using default ensemble weights")


# Starting weights per coin (will be refined by optimizer)
COIN_DEFAULT_WEIGHTS = {
    "BTC":  {"autogluon": 0.50, "lstm": 0.25, "xgboost": 0.25},
    "ETH":  {"autogluon": 0.45, "lstm": 0.30, "xgboost": 0.25},
    "SOL":  {"autogluon": 0.40, "lstm": 0.35, "xgboost": 0.25},
    "DOGE": {"autogluon": 0.35, "lstm": 0.40, "xgboost": 0.25},  # LSTM higher: meme momentum
    "XRP":  {"autogluon": 0.45, "lstm": 0.30, "xgboost": 0.25},
}
DEFAULT_WEIGHTS = {"autogluon": 0.45, "lstm": 0.30, "xgboost": 0.25}


class EnsemblePredictor:
    def __init__(self, coin, horizon_hours=1):
        self.coin = coin
        self.horizon_hours = horizon_hours
        self.horizon_str = f"{horizon_hours}h"

        self.models = {
            "autogluon": AutoGluonModel(coin, self.horizon_str),
            "lstm": LSTMModel(coin, self.horizon_str),
            "xgboost": XGBoostModel(coin, self.horizon_str),
        }

        # Load per-coin optimized weights if available, else use defaults
        self.weights = self._load_weights()

        self.weights_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"ensemble_weights_{coin}_{self.horizon_str}.json"
        )

    def _load_weights(self):
        weights_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR,
            f"ensemble_weights_{self.coin}_{self.horizon_str}.json",
        )
        if os.path.exists(weights_path):
            try:
                with open(weights_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return COIN_DEFAULT_WEIGHTS.get(self.coin, DEFAULT_WEIGHTS)

    def optimize_weights(self, val_df, feature_columns, target_column):
        """
        Learn optimal ensemble weights on validation data using scipy.optimize.
        Saves optimized weights to disk for future use.
        """
        if not SCIPY_AVAILABLE:
            logger.warning("scipy not available — using default weights")
            return self.weights

        logger.info(f"Optimizing ensemble weights for {self.coin}...")

        # Collect probability predictions from each model on validation data
        model_probas = {}
        for name, model in self.models.items():
            try:
                if name == "autogluon":
                    preds = []
                    for i in range(len(val_df)):
                        row = val_df.iloc[i:i+1][feature_columns]
                        pred = model.predict(row)
                        preds.append(pred["probabilities"]["UP"] if pred else 0.5)
                    model_probas[name] = np.array(preds)
                elif name == "lstm":
                    # HIGH-05 FIX: Start from seq_len index so the LSTM always has
                    # a full context window. Earlier rows returned None (→ 0.5 fallback)
                    # which biased the weight optimization against LSTM.
                    preds = []
                    seq_len = model.sequence_length
                    full_df = val_df[feature_columns]
                    for i in range(seq_len, len(val_df)):
                        window = full_df.iloc[i - seq_len: i + 1]
                        pred = model.predict(window)
                        preds.append(pred["probabilities"]["UP"] if pred else 0.5)
                    # Pad the front with the first real prediction to keep array length
                    if preds:
                        preds = [preds[0]] * seq_len + preds
                    else:
                        preds = [0.5] * len(val_df)
                    model_probas[name] = np.array(preds)
                else:
                    avail = [c for c in feature_columns if c in val_df.columns]
                    proba = model.model.predict_proba(
                        val_df[avail].fillna(0).replace([np.inf, -np.inf], 0)
                    )
                    model_probas[name] = proba[:, 1]
            except Exception as e:
                logger.warning(f"Could not get {name} probas for weight opt: {e}")

        if len(model_probas) < 2:
            logger.warning("Not enough model predictions for weight optimization")
            return self.weights

        y_val = val_df[target_column].values
        model_names = list(model_probas.keys())
        probas_matrix = np.stack([model_probas[n] for n in model_names], axis=1)

        def neg_accuracy(weights):
            w = np.abs(weights) / (np.abs(weights).sum() + 1e-9)
            combined = probas_matrix @ w
            preds = (combined > 0.5).astype(int)
            return -np.mean(preds == y_val)

        x0 = [self.weights.get(n, 1/3) for n in model_names]
        result = minimize(neg_accuracy, x0=x0, method="Nelder-Mead",
                          options={"maxiter": 1000, "xatol": 1e-4})

        optimal = np.abs(result.x) / (np.abs(result.x).sum() + 1e-9)
        optimized_weights = {n: round(float(w), 4) for n, w in zip(model_names, optimal)}

        best_acc = -result.fun
        logger.info(
            f"Ensemble {self.coin}: optimized weights = {optimized_weights}, "
            f"val accuracy = {best_acc:.4f}"
        )

        # Persist
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)
        with open(self.weights_path, "w") as f:
            json.dump(optimized_weights, f, indent=2)

        self.weights = optimized_weights
        return optimized_weights

    def predict(self, features_df, current_price=None):
        predictions = {}

        for name, model in self.models.items():
            try:
                result = model.predict(features_df)
                if result:
                    predictions[name] = result
                    logger.info(
                        f"{self.coin} {name}: {result['direction']} "
                        f"({result['confidence']:.2%})"
                    )
            except Exception as e:
                logger.warning(f"Model {name} failed for {self.coin}: {e}")

        if not predictions:
            return None

        # --- Agreement filter ---
        directions = [p["direction"] for p in predictions.values()]
        up_votes = directions.count("UP")
        down_votes = directions.count("DOWN")
        total_votes = len(directions)

        # Require at least 2/3 consensus (majority)
        if total_votes >= 2:
            if up_votes < 2 and down_votes < 2:
                # No majority — return HOLD signal
                return {
                    "direction": "SIDEWAYS",
                    "confidence": 0.0,
                    "signal_type": "HOLD",
                    "reason": "no_model_agreement",
                    "model": "ensemble",
                    "individual_predictions": predictions,
                }

        # --- Weighted probability aggregation ---
        total_weight = 0
        bull_score = 0.0
        bear_score = 0.0

        for name, pred in predictions.items():
            weight = self.weights.get(name, 1 / len(predictions))
            total_weight += weight
            prob_up = pred["probabilities"].get("UP", 0.5)
            prob_down = pred["probabilities"].get("DOWN", 0.5)
            bull_score += weight * prob_up
            bear_score += weight * prob_down

        if total_weight > 0:
            bull_score /= total_weight
            bear_score /= total_weight

        if bull_score > bear_score:
            direction = "UP"
            confidence = bull_score
        else:
            direction = "DOWN"
            confidence = bear_score

        # Boost confidence on full agreement
        full_agreement = len(set(directions)) == 1
        majority_agreement = up_votes >= 2 or down_votes >= 2

        if full_agreement:
            confidence = min(confidence * 1.15, 0.95)
        elif not majority_agreement:
            confidence *= 0.75

        # --- Confidence gate ---
        if confidence < MIN_SIGNAL_CONFIDENCE:
            return {
                "direction": direction,
                "confidence": round(confidence, 4),
                "signal_type": "HOLD",
                "reason": f"low_confidence_{confidence:.3f}",
                "model": "ensemble",
                "individual_predictions": predictions,
            }

        # Determine signal type
        if direction == "UP":
            signal_type = "STRONG_BUY" if confidence > 0.75 else "BUY"
        else:
            signal_type = "STRONG_SELL" if confidence > 0.75 else "SELL"

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "signal_type": signal_type,
            "bull_score": round(bull_score, 4),
            "bear_score": round(bear_score, 4),
            "full_agreement": full_agreement,
            "majority_agreement": majority_agreement,
            "models_used": len(predictions),
            "individual_predictions": predictions,
            "weights_used": self.weights,
            "model": "ensemble",
        }

    def load_all(self):
        """Pre-load all sub-models for fast hourly predictions."""
        for name, model in self.models.items():
            try:
                model.load()
            except Exception as e:
                logger.warning(f"Could not pre-load {name} for {self.coin}: {e}")
