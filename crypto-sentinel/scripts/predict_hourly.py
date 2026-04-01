#!/usr/bin/env python
"""
Hourly prediction runner — runs ensemble predictions for all 3 horizons (1h, 4h, 24h).

Designed to be called every hour via:
  - APScheduler (inside pipeline_orchestrator.py)
  - Cron: 0 * * * * cd /app && python scripts/predict_hourly.py
  - Manual: python scripts/predict_hourly.py --coin BTC

Stores predictions for each horizon in the signals table with horizon info in reasoning.
Expected runtime: ~15-30 seconds per coin (all models pre-loaded)
"""
import sys
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config.coins import TRACKED_COINS
from config.settings import settings
from config.constants import MIN_SIGNAL_CONFIDENCE
from database.connection import get_engine
from features.feature_engineer import FeatureEngineer
from models.ensemble import EnsemblePredictor
from sqlalchemy import text


def run_prediction(coin, engine=None, horizons=None):
    """Run ensemble predictions for one coin across all horizons.
    Returns a dict of {horizon_str: prediction_result}."""
    if engine is None:
        engine = get_engine()
    if horizons is None:
        horizons = settings.PREDICTION_HORIZONS  # [1, 4, 24]

    fe = FeatureEngineer()

    # Build features from last 48h of 1h candles (enough for 24-step LSTM lookback)
    df = fe.build_prediction_features(coin, interval="1h", lookback_hours=72)
    if df is None or df.empty:
        logger.warning(f"No feature data for {coin} — skipping prediction")
        return None

    feature_cols = [c for c in fe.get_feature_columns() if c in df.columns]

    # Fetch current price from Binance
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

    results = {}

    for horizon_hours in horizons:
        h_key = f"{horizon_hours}h"
        logger.info(f"  {coin}/{h_key}: Running ensemble prediction...")

        try:
            ensemble = EnsemblePredictor(coin, horizon_hours=horizon_hours)
            ensemble.load_all()
            prediction = ensemble.predict(df[feature_cols], current_price=current_price)
        except Exception as e:
            logger.warning(f"  {coin}/{h_key}: Ensemble error — {e}")
            prediction = None

        if prediction is None:
            logger.warning(f"  {coin}/{h_key}: No prediction returned")
            continue

        signal_type = prediction.get("signal_type", "HOLD")
        confidence = prediction.get("confidence", 0.0)
        direction = prediction.get("direction", "SIDEWAYS")

        logger.info(
            f"  {coin}/{h_key}: {signal_type} | dir={direction} | "
            f"conf={confidence:.2%} | models={prediction.get('models_used', 0)} | "
            f"agreement={'✓' if prediction.get('majority_agreement') else '✗'}"
        )

        # Store individual model predictions in reasoning
        individual_preds_json = json.dumps({
            k: {"direction": v["direction"], "confidence": v["confidence"]}
            for k, v in prediction.get("individual_predictions", {}).items()
        })
        reasoning_str = f"[{h_key}] {prediction.get('reason', 'ensemble_vote')} | {individual_preds_json}"

        # Save to signals table
        insert_sql = text("""
            INSERT INTO signals
                (coin, signal_type, confidence, generated_at, price_at_signal,
                 sentiment_score, prediction_score, onchain_score, technical_score,
                 divergence_signal, reasoning)
            VALUES
                (:coin, :signal_type, :confidence, :generated_at, :price_at_signal,
                 :sentiment_score, :prediction_score, :onchain_score, :technical_score,
                 :divergence_signal, :reasoning)
        """)
        try:
            with engine.begin() as conn:
                conn.execute(insert_sql, {
                    "coin": coin,
                    "signal_type": f"{signal_type}_{h_key}",
                    "confidence": confidence,
                    "generated_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                    "price_at_signal": current_price,
                    "sentiment_score": float(df["avg_sentiment"].iloc[-1]) if "avg_sentiment" in df.columns else 0.5,
                    "prediction_score": confidence,
                    "onchain_score": float(df["whale_activity_score"].iloc[-1]) if "whale_activity_score" in df.columns else 0.5,
                    "technical_score": float(df["rsi"].iloc[-1]) / 100 if "rsi" in df.columns else 0.5,
                    "divergence_signal": "NONE",
                    "reasoning": reasoning_str[:2000],
                })
        except Exception as e:
            logger.error(f"Signal save error for {coin}/{h_key}: {e}")

        results[h_key] = prediction

    return results


def main():
    parser = argparse.ArgumentParser(description="Crypto Sentinel — Multi-Horizon Predictor")
    parser.add_argument("--coin", default=None,
                        help="Single coin to predict (default: all tracked coins)")
    parser.add_argument("--horizons", default="1,4,24",
                        help="Comma-separated horizons in hours (default: 1,4,24)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print prediction without saving to DB")
    args = parser.parse_args()

    horizons = [int(h.strip()) for h in args.horizons.split(",")]
    engine = get_engine() if not args.dry_run else None
    coins = [args.coin.upper()] if args.coin else list(TRACKED_COINS.keys())

    logger.info(f"Running predictions: coins={coins} horizons={[f'{h}h' for h in horizons]}")

    for coin in coins:
        if coin not in TRACKED_COINS:
            logger.error(f"Unknown coin: {coin}")
            continue
        try:
            results = run_prediction(coin, engine=engine, horizons=horizons)
            if results and args.dry_run:
                print(f"\n{coin} predictions (dry-run):")
                for h_key, pred in results.items():
                    print(f"  {h_key}: {pred.get('direction')} ({pred.get('confidence', 0):.2%})")
        except Exception as e:
            logger.error(f"Prediction failed for {coin}: {e}")


if __name__ == "__main__":
    main()
