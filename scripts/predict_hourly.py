#!/usr/bin/env python
"""
Hourly prediction runner — fetches latest candles, runs ensemble, stores signal.

Designed to be called every hour via:
  - APScheduler (inside pipeline_orchestrator.py)
  - Cron: 0 * * * * cd /app && python scripts/predict_hourly.py
  - Manual: python scripts/predict_hourly.py --coin BTC

Expected runtime: ~5-15 seconds per coin (all models pre-loaded)
"""
import sys
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config.coins import TRACKED_COINS
from config.constants import MIN_SIGNAL_CONFIDENCE
from database.connection import get_engine
from features.feature_engineer import FeatureEngineer
from models.ensemble import EnsemblePredictor
from sqlalchemy import text


def run_prediction(coin, engine=None):
    """Run ensemble prediction for one coin and return signal dict."""
    if engine is None:
        engine = get_engine()

    fe = FeatureEngineer()

    # Build features from last 48h of 1h candles (more than enough for 24-step LSTM lookback)
    df = fe.build_prediction_features(coin, interval="1h", lookback_hours=48)
    if df is None or df.empty:
        logger.warning(f"No feature data for {coin} — skipping prediction")
        return None

    feature_cols = [c for c in fe.get_feature_columns() if c in df.columns]

    # Load ensemble (uses already-trained artifacts)
    ensemble = EnsemblePredictor(coin, horizon_hours=1)
    ensemble.load_all()

    # Fetch current price
    try:
        import requests
        symbol = TRACKED_COINS[coin]["binance_symbol"]
        price_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": symbol}, timeout=5,
        )
        current_price = float(price_resp.json()["price"])
    except Exception:
        current_price = float(df["close"].iloc[-1]) if not df.empty else None

    prediction = ensemble.predict(df[feature_cols], current_price=current_price)
    if prediction is None:
        logger.warning(f"Ensemble returned None for {coin}")
        return None

    signal_type = prediction.get("signal_type", "HOLD")
    confidence = prediction.get("confidence", 0.0)
    direction = prediction.get("direction", "SIDEWAYS")

    logger.info(
        f"{coin}: {signal_type} | direction={direction} | "
        f"confidence={confidence:.2%} | "
        f"models={prediction.get('models_used', 0)} | "
        f"agreement={'✓' if prediction.get('majority_agreement') else '✗'}"
    )

    # Persist to signals table
    insert_sql = text("""
        INSERT INTO signals
            (coin, signal_type, confidence, generated_at, price_at_signal,
             sentiment_score, prediction_score, onchain_score, technical_score,
             reasoning, model_predictions)
        VALUES
            (:coin, :signal_type, :confidence, :generated_at, :price_at_signal,
             :sentiment_score, :prediction_score, :onchain_score, :technical_score,
             :reasoning, :model_predictions)
    """)
    try:
        with engine.begin() as conn:
            conn.execute(insert_sql, {
                "coin": coin,
                "signal_type": signal_type,
                "confidence": confidence,
                "generated_at": datetime.now(timezone.utc),
                "price_at_signal": current_price,
                "sentiment_score": float(df.get("avg_sentiment", [0.5]).iloc[-1]) if "avg_sentiment" in df.columns else 0.5,
                "prediction_score": confidence,
                "onchain_score": float(df.get("whale_activity_score", [0.5]).iloc[-1]) if "whale_activity_score" in df.columns else 0.5,
                "technical_score": float(df.get("rsi", [50]).iloc[-1]) / 100 if "rsi" in df.columns else 0.5,
                "reasoning": prediction.get("reason", "ensemble_vote"),
                "model_predictions": json.dumps({
                    k: {"direction": v["direction"], "confidence": v["confidence"]}
                    for k, v in prediction.get("individual_predictions", {}).items()
                }),
            })
    except Exception as e:
        logger.error(f"Signal save error for {coin}: {e}")

    return prediction


def main():
    parser = argparse.ArgumentParser(description="Crypto Sentinel — Hourly Predictor")
    parser.add_argument("--coin", default=None,
                        help="Single coin to predict (default: all tracked coins)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prediction without saving to DB")
    args = parser.parse_args()

    engine = get_engine() if not args.dry_run else None
    coins = [args.coin.upper()] if args.coin else list(TRACKED_COINS.keys())

    for coin in coins:
        if coin not in TRACKED_COINS:
            logger.error(f"Unknown coin: {coin}")
            continue
        try:
            result = run_prediction(coin, engine=engine)
            if result and args.dry_run:
                print(f"\n{coin} prediction (dry-run):")
                print(json.dumps(result, indent=2, default=str))
        except Exception as e:
            logger.error(f"Prediction failed for {coin}: {e}")


if __name__ == "__main__":
    main()
