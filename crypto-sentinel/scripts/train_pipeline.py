#!/usr/bin/env python
"""
One-shot training pipeline for all 5 crypto coins.

Usage:
    python scripts/train_pipeline.py
    python scripts/train_pipeline.py --coins BTC,ETH --days 90 --ag-time 600

Steps per coin:
  1. Fetch 90 days of 1h historical candles from Binance → DB
  2. Engineer 50+ features
  3. Train AutoGluon (TabularPredictor, good_quality, 10 min)
  4. Train XGBoost with Optuna (30 trials, GPU)
  5. Train LSTM with Optuna (15 trials, GPU)
  6. Optimize ensemble weights on validation split (scipy)
  7. Print accuracy report

Total expected time: ~60-80 min for all 5 coins on i5-8300H + GTX 1650
"""
import sys
import os
import argparse
import time
import requests
import json
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from config.coins import TRACKED_COINS
from config.constants import TRAINING_WINDOW_DAYS, PREDICTION_INTERVAL
from database.connection import get_engine
from features.feature_engineer import FeatureEngineer
from models.autogluon_model import AutoGluonModel
from models.xgboost_model import XGBoostModel
from models.lstm_model import LSTMModel
from models.ensemble import EnsemblePredictor
from sqlalchemy import text


# ─────────────────────────────────────────────
# Historical data bootstrap
# ─────────────────────────────────────────────
BINANCE_BASE = "https://api.binance.com"


def fetch_1h_historical(symbol, days=90):
    """Fetch `days` worth of 1h OHLCV candles from Binance public API (no key needed)."""
    candles_needed = days * 24
    all_records = []
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    while len(all_records) < candles_needed:
        limit = min(1000, candles_needed - len(all_records))
        try:
            r = requests.get(
                f"{BINANCE_BASE}/api/v3/klines",
                params={"symbol": symbol, "interval": "1h", "limit": limit, "endTime": end_ms},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            logger.error(f"Binance fetch error for {symbol}: {e}")
            break

        if not data:
            break

        for c in data:
            all_records.append({
                "timestamp": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
                "quote_volume": float(c[7]),
                "num_trades": int(c[8]),
            })

        end_ms = data[0][0] - 1  # next batch ends before oldest in this batch
        if len(data) < limit:
            break  # no more data

    all_records.sort(key=lambda x: x["timestamp"])
    logger.info(f"Fetched {len(all_records)} 1h candles for {symbol}")
    return all_records


def save_price_records(engine, coin_symbol, records, interval="1h"):
    """Batch upsert price records."""
    if not records:
        return 0

    insert_sql = text("""
        INSERT INTO price_data
            (coin, interval, timestamp, open, high, low, close, volume, quote_volume, num_trades)
        VALUES
            (:coin, :interval, :timestamp, :open, :high, :low, :close, :volume, :quote_volume, :num_trades)
        ON CONFLICT (coin, interval, timestamp) DO NOTHING
    """)
    saved = 0
    try:
        with engine.begin() as conn:
            for rec in records:
                try:
                    conn.execute(insert_sql, {"coin": coin_symbol, "interval": interval, **rec})
                    saved += 1
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Batch price insert error: {e}")

    logger.info(f"Saved {saved}/{len(records)} price records for {coin_symbol} ({interval})")
    return saved


# ─────────────────────────────────────────────
# Main training loop
# ─────────────────────────────────────────────
def train_coin(
    coin,
    days=90,
    ag_time_limit=600,
    xgb_optuna_trials=30,
    lstm_optuna_trials=15,
    engine=None,
):
    logger.info(f"\n{'='*60}")
    logger.info(f"  TRAINING: {coin}  ({days}d historical, 1h interval)")
    logger.info(f"{'='*60}")
    t_start = time.time()

    # Step 1 — Bootstrap historical data
    binance_symbol = TRACKED_COINS[coin]["binance_symbol"]
    logger.info(f"[1/6] Fetching {days}d 1h candles for {binance_symbol}...")
    records = fetch_1h_historical(binance_symbol, days=days)
    if engine:
        save_price_records(engine, coin, records, interval="1h")

    # Step 2 — Feature engineering
    logger.info(f"[2/6] Engineering features for {coin}...")
    fe = FeatureEngineer()
    df = fe.build_training_features(coin, interval="1h", days=days)
    if df is None or len(df) < 100:
        logger.error(f"Not enough data for {coin} — skipping")
        return None

    feature_cols = [c for c in fe.get_feature_columns() if c in df.columns]
    target_col = "target_1h"

    # Time-ordered validation split (last 20%)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    logger.info(f"  Train: {len(train_df)} rows | Val: {len(val_df)} rows | Features: {len(feature_cols)}")

    results = {"coin": coin, "n_train": len(train_df), "n_val": len(val_df)}

    # Step 3 — AutoGluon
    logger.info(f"[3/6] Training AutoGluon (time_limit={ag_time_limit}s)...")
    ag_model = AutoGluonModel(coin, horizon="1h")
    ag_meta = ag_model.train(train_df, feature_cols, target_col, time_limit=ag_time_limit)
    results["autogluon"] = ag_meta or {}

    # Step 4 — XGBoost + Optuna
    logger.info(f"[4/6] Training XGBoost (Optuna trials={xgb_optuna_trials})...")
    xgb_model = XGBoostModel(coin, horizon="1h")
    xgb_meta = xgb_model.train(train_df, feature_cols, target_col, n_optuna_trials=xgb_optuna_trials)
    results["xgboost"] = xgb_meta or {}

    # Step 5 — LSTM + Optuna
    logger.info(f"[5/6] Training LSTM (Optuna trials={lstm_optuna_trials})...")
    lstm_model = LSTMModel(coin, horizon="1h")
    lstm_meta = lstm_model.train(train_df, feature_cols, target_col, n_optuna_trials=lstm_optuna_trials)
    results["lstm"] = lstm_meta or {}

    # Step 6 — Optimize ensemble weights
    logger.info(f"[6/6] Optimizing ensemble weights on validation set...")
    ensemble = EnsemblePredictor(coin, horizon_hours=1)
    ensemble.models["autogluon"] = ag_model
    ensemble.models["xgboost"] = xgb_model
    ensemble.models["lstm"] = lstm_model
    optimized = ensemble.optimize_weights(val_df, feature_cols, target_col)
    results["ensemble_weights"] = optimized

    elapsed = time.time() - t_start
    results["train_time_seconds"] = round(elapsed)

    # Print summary table
    logger.info(f"\n{'─'*50}")
    logger.info(f"  RESULTS: {coin}")
    logger.info(f"{'─'*50}")
    if ag_meta:
        logger.info(f"  AutoGluon  val_acc: {ag_meta.get('val_accuracy', 'N/A')}")
    if xgb_meta:
        logger.info(f"  XGBoost    val_acc: {xgb_meta.get('val_accuracy', 'N/A')}  "
                    f"(CV: {xgb_meta.get('cv_accuracy_mean', 'N/A')} ± {xgb_meta.get('cv_accuracy_std', 'N/A')})")
    if lstm_meta:
        logger.info(f"  LSTM       val_acc: {lstm_meta.get('val_accuracy', 'N/A')}")
    logger.info(f"  Weights:   {optimized}")
    logger.info(f"  Time:      {elapsed:.0f}s")

    return results


def main():
    parser = argparse.ArgumentParser(description="Crypto Sentinel Training Pipeline")
    parser.add_argument("--coins", default=",".join(TRACKED_COINS.keys()),
                        help="Comma-separated coin symbols (default: all)")
    parser.add_argument("--days", type=int, default=TRAINING_WINDOW_DAYS,
                        help="Training window in days (default: 90)")
    parser.add_argument("--ag-time", type=int, default=600,
                        help="AutoGluon time_limit per coin in seconds (default: 600)")
    parser.add_argument("--xgb-trials", type=int, default=30,
                        help="Optuna trials for XGBoost (default: 30)")
    parser.add_argument("--lstm-trials", type=int, default=15,
                        help="Optuna trials for LSTM (default: 15)")
    parser.add_argument("--skip-historical", action="store_true",
                        help="Skip Binance historical fetch (use existing DB data)")
    args = parser.parse_args()

    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    invalid = [c for c in coins if c not in TRACKED_COINS]
    if invalid:
        logger.error(f"Unknown coins: {invalid}. Valid: {list(TRACKED_COINS.keys())}")
        sys.exit(1)

    engine = get_engine()
    all_results = {}
    overall_start = time.time()

    logger.info(f"Training pipeline starting for: {coins}")
    logger.info(f"  Training window: {args.days} days | Interval: 1h")
    logger.info(f"  AutoGluon time_limit: {args.ag_time}s | XGB Optuna: {args.xgb_trials} | LSTM Optuna: {args.lstm_trials}")

    for coin in coins:
        try:
            result = train_coin(
                coin,
                days=args.days,
                ag_time_limit=args.ag_time,
                xgb_optuna_trials=args.xgb_trials,
                lstm_optuna_trials=args.lstm_trials,
                engine=engine if not args.skip_historical else None,
            )
            all_results[coin] = result
        except Exception as e:
            logger.error(f"Training failed for {coin}: {e}")
            all_results[coin] = {"error": str(e)}

    total_time = time.time() - overall_start
    logger.info(f"\n{'='*60}")
    logger.info(f"  TRAINING COMPLETE — {len(coins)} coins in {total_time/60:.1f} min")
    logger.info(f"{'='*60}")

    # Save overall report
    report_path = "model_artifacts/training_report.json"
    os.makedirs("model_artifacts", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info(f"Full report saved to: {report_path}")


if __name__ == "__main__":
    main()
