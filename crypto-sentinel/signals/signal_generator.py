import json
from datetime import datetime, timezone
from loguru import logger
from models.ensemble import EnsemblePredictor
from signals.fear_greed_index import FearGreedIndex
from signals.sentiment_momentum import SentimentMomentum
from signals.divergence_detector import DivergenceDetector
from features.feature_engineer import FeatureEngineer
from database.connection import get_engine
from config.coins import TRACKED_COINS
from config.constants import BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL
import pandas as pd


class SignalGenerator:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.fear_greed = FearGreedIndex()
        self.momentum = SentimentMomentum()
        self.divergence = DivergenceDetector()
        self.engine = get_engine()

    def generate_signal(self, coin):
        features_df = self.feature_engineer.build_prediction_features(coin, interval="1h", lookback_hours=72)

        # Try all 3 horizons, use 1h as primary
        prediction = None
        all_predictions = {}
        for h in [1, 4, 24]:
            try:
                ens = EnsemblePredictor(coin, horizon_hours=h)
                ens.load_all()
                feat_cols = [c for c in self.feature_engineer.get_feature_columns() if c in features_df.columns] if features_df is not None else []
                pred = ens.predict(features_df[feat_cols] if features_df is not None and feat_cols else features_df)
                if pred and pred.get("confidence", 0) > 0:
                    all_predictions[f"{h}h"] = pred
                    if h == 1:
                        prediction = pred
            except Exception as e:
                logger.warning(f"Ensemble prediction {h}h for {coin}: {e}")

        # Fallback: try 4h if 1h failed
        if prediction is None and "4h" in all_predictions:
            prediction = all_predictions["4h"]
        elif prediction is None and "24h" in all_predictions:
            prediction = all_predictions["24h"]

        if prediction is None:
            logger.warning(f"No prediction available for {coin}")
            return None

        # Sentiment — parameterized query (MED-02)
        sent_df = pd.read_sql(
            """SELECT avg_sentiment, social_volume, sentiment_velocity FROM sentiment_aggregated
            WHERE coin = :coin AND window_size = '4h' ORDER BY window_start DESC LIMIT 1""",
            self.engine, params={"coin": coin},
        )
        sentiment_score = float(sent_df.iloc[0]["avg_sentiment"]) if not sent_df.empty else 0.5

        # On-chain
        onchain_df = pd.read_sql(
            """SELECT net_flow_usd, whale_activity_score FROM onchain_metrics
            WHERE coin = :coin ORDER BY timestamp DESC LIMIT 1""",
            self.engine, params={"coin": coin},
        )
        whale_accumulating = False
        onchain_score = 0.5
        if not onchain_df.empty:
            net_flow = float(onchain_df.iloc[0]["net_flow_usd"] or 0)
            whale_accumulating = net_flow > 0
            onchain_score = float(onchain_df.iloc[0]["whale_activity_score"] or 0.5)

        # Technical
        tech_df = pd.read_sql(
            """SELECT rsi, macd_histogram FROM technical_indicators
            WHERE coin = :coin ORDER BY timestamp DESC LIMIT 1""",
            self.engine, params={"coin": coin},
        )
        technical_score = 0.5
        if not tech_df.empty:
            rsi = float(tech_df.iloc[0]["rsi"] or 50)
            if rsi < 30:
                technical_score = 0.8
            elif rsi > 70:
                technical_score = 0.2
            else:
                technical_score = 0.5 + (0.5 - rsi / 100) * 0.3

        # HIGH-04 FIX: DOWN prediction now pushes score below 0.5 instead of contributing 0.
        # pred_score = confidence if UP, = (1 - confidence) if DOWN.
        pred_score = (
            prediction["confidence"]
            if prediction["direction"] == "UP"
            else (1 - prediction["confidence"])
        )
        composite = (
            sentiment_score * 0.30
            + pred_score * 0.30
            + onchain_score * 0.20
            + technical_score * 0.20
        )

        # Signal type
        reasoning_parts = []
        if composite > 0.75:
            signal_type = STRONG_BUY
        elif composite > 0.60:
            signal_type = BUY
        elif composite < 0.25:
            signal_type = STRONG_SELL
        elif composite < 0.40:
            signal_type = SELL
        else:
            signal_type = HOLD

        reasoning_parts.extend([
            f"Composite score: {composite:.2f}",
            f"Sentiment: {sentiment_score:.2f} ({'Bullish' if sentiment_score > 0.6 else 'Bearish' if sentiment_score < 0.4 else 'Neutral'})",
            f"Prediction: {prediction['direction']} ({prediction['confidence']:.0%}, {prediction.get('models_used', '?')} models)",
            f"Model Agreement: {'✅' if prediction.get('majority_agreement') else '⚠️'}",
            f"Whales: {'Accumulating 🟢' if whale_accumulating else 'Distributing 🔴'}",
        ])

        # Momentum
        momentum = self.momentum.calculate(coin)
        reasoning_parts.append(f"Momentum: {momentum['signal']}")

        # Divergence override
        divergence = self.divergence.detect(coin)
        if divergence["divergence_type"] != "NONE":
            reasoning_parts.append(f"DIVERGENCE: {divergence['divergence_type']} (strength: {divergence['strength']:.2f})")
            if divergence["divergence_type"] == "BULLISH_DIVERGENCE" and signal_type in [HOLD, SELL]:
                signal_type = BUY
                reasoning_parts.append("Signal upgraded due to bullish divergence")
            elif divergence["divergence_type"] == "BEARISH_DIVERGENCE" and signal_type in [HOLD, BUY]:
                signal_type = SELL
                reasoning_parts.append("Signal downgraded due to bearish divergence")

        # Current price
        price_df = pd.read_sql(
            "SELECT close FROM price_data WHERE coin = :coin ORDER BY timestamp DESC LIMIT 1",
            self.engine, params={"coin": coin},
        )
        current_price = float(price_df.iloc[0]["close"]) if not price_df.empty else 0

        signal = {
            "coin": coin,
            "signal_type": signal_type,
            "confidence": round(composite, 4),
            "generated_at": datetime.now(timezone.utc),
            "sentiment_score": round(sentiment_score, 4),
            "prediction_score": round(prediction["confidence"], 4),
            "onchain_score": round(onchain_score, 4),
            "technical_score": round(technical_score, 4),
            "divergence_signal": divergence["divergence_type"],
            "reasoning": json.dumps(reasoning_parts),
            "price_at_signal": current_price,
        }

        try:
            pd.DataFrame([signal]).to_sql("signals", self.engine, if_exists="append", index=False)
        except Exception as e:
            logger.error(f"Signal save error: {e}")

        # Save prediction record
        try:
            pred_record = {
                "coin": coin, "predicted_at": datetime.now(timezone.utc),
                "horizon_hours": 1, "predicted_direction": prediction["direction"],
                "confidence": prediction["confidence"], "model_name": "ensemble",
                "features_used": json.dumps(list(prediction["individual_predictions"].keys())),
            }
            pd.DataFrame([pred_record]).to_sql("predictions", self.engine, if_exists="append", index=False)
        except Exception:
            pass

        logger.info(f"Signal for {coin}: {signal_type} (confidence: {composite:.2%})")
        return signal

    def generate_all_signals(self):
        signals = []
        for coin in TRACKED_COINS.keys():
            try:
                signal = self.generate_signal(coin)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Signal generation failed for {coin}: {e}")
        return signals
