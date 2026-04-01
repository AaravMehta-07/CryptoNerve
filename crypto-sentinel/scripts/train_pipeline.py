#!/usr/bin/env python
"""
One-shot training pipeline for all 5 crypto coins × 3 prediction horizons.

Usage:
    python scripts/train_pipeline.py
    python scripts/train_pipeline.py --coins BTC,ETH --days 90 --ag-time 300
    python scripts/train_pipeline.py --coins BTC --horizons 1,4,24

Steps per coin per horizon:
  1. Fetch 90 days of 1h historical candles from Binance → DB
  2. Engineer 50+ features + multi-horizon targets (1h, 4h, 24h)
  3. Train AutoGluon (TabularPredictor, good_quality)
  4. Train XGBoost with Optuna (30 trials)
  5. Train LSTM with Optuna (15 trials)
  6. Optimize ensemble weights on validation split (scipy)
  7. Print accuracy report

All model artifacts are saved to: trained_models/
Copy this folder to transfer trained models between machines.

Estimated time (Ryzen 7 8c/16t + RTX 3060):
  ~15 min/coin × 3 horizons = ~45 min/coin
  All 5 coins ≈ ~3.5-4 hours
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
from config.constants import TRAINING_WINDOW_DAYS
from config.settings import settings
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
                "timestamp": datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })

        end_ms = data[0][0] - 1
        if len(data) < limit:
            break

    all_records.sort(key=lambda x: x["timestamp"])
    logger.info(f"Fetched {len(all_records)} 1h candles for {symbol}")
    return all_records


def save_price_records(engine, coin_symbol, records, interval="1h"):
    """Batch upsert price records."""
    if not records:
        return 0

    insert_sql = text("""
        INSERT INTO price_data
            (coin, interval, timestamp, open, high, low, close, volume)
        VALUES
            (:coin, :interval, :timestamp, :open, :high, :low, :close, :volume)
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
# Main training loop — multi-horizon
# ─────────────────────────────────────────────
def train_coin(
    coin,
    days=90,
    horizons=None,
    ag_time_limit=300,
    xgb_optuna_trials=30,
    lstm_optuna_trials=15,
    engine=None,
):
    if horizons is None:
        horizons = settings.PREDICTION_HORIZONS  # [1, 4, 24]

    logger.info(f"\n{'='*60}")
    logger.info(f"  TRAINING: {coin}  ({days}d data, horizons: {horizons})")
    logger.info(f"{'='*60}")
    t_start = time.time()

    # Step 1 — Bootstrap historical data from Binance
    binance_symbol = TRACKED_COINS[coin]["binance_symbol"]
    if engine:
        logger.info(f"[1/7] Fetching {days}d 1h candles for {binance_symbol}...")
        records = fetch_1h_historical(binance_symbol, days=days)
        save_price_records(engine, coin, records, interval="1h")
    else:
        logger.info(f"[1/7] Skipping historical fetch (--skip-historical)")

    # Step 2 — Feature engineering (builds targets for ALL horizons at once)
    logger.info(f"[2/7] Engineering features for {coin}...")
    fe = FeatureEngineer()
    df = fe.build_training_features(coin, interval="1h", days=days)
    if df is None or len(df) < 100:
        logger.error(f"Not enough data for {coin} — skipping")
        return None

    feature_cols = [c for c in fe.get_feature_columns() if c in df.columns]
    logger.info(f"  Total rows: {len(df)} | Features: {len(feature_cols)}")

    # Time-ordered validation split (last 20%)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    val_df = df.iloc[split_idx:]
    logger.info(f"  Train: {len(train_df)} rows | Val: {len(val_df)} rows")

    results = {
        "coin": coin,
        "n_train": len(train_df),
        "n_val": len(val_df),
        "n_features": len(feature_cols),
        "horizons": {},
    }

    # Steps 3-6 — Train per horizon
    for h_idx, horizon_hours in enumerate(horizons):
        target_col = f"target_{horizon_hours}h"
        if target_col not in df.columns:
            logger.warning(f"Target column {target_col} missing, skipping")
            continue

        h_key = f"{horizon_hours}h"
        step_base = 3
        logger.info(f"\n{'─'*50}")
        logger.info(f"  {coin} / {h_key} Horizon  (target: {target_col})")
        logger.info(f"{'─'*50}")

        horizon_result = {}
        ag_model, xgb_model, lstm_model = None, None, None
        ag_meta, xgb_meta, lstm_meta = None, None, None

        # AutoGluon
        logger.info(f"[{step_base}/7] Training AutoGluon {h_key} (time_limit={ag_time_limit}s)...")
        try:
            ag_model = AutoGluonModel(coin, horizon=h_key)
            ag_meta = ag_model.train(train_df, feature_cols, target_col, time_limit=ag_time_limit)
            horizon_result["autogluon"] = ag_meta or {}
        except Exception as e:
            logger.error(f"AutoGluon {h_key} failed: {e}")
            horizon_result["autogluon"] = {"error": str(e)}

        # XGBoost + Optuna
        logger.info(f"[{step_base+1}/7] Training XGBoost {h_key} (Optuna trials={xgb_optuna_trials})...")
        try:
            xgb_model = XGBoostModel(coin, horizon=h_key)
            xgb_meta = xgb_model.train(train_df, feature_cols, target_col, n_optuna_trials=xgb_optuna_trials)
            horizon_result["xgboost"] = xgb_meta or {}
        except Exception as e:
            logger.error(f"XGBoost {h_key} failed: {e}")
            horizon_result["xgboost"] = {"error": str(e)}

        # LSTM + Optuna
        logger.info(f"[{step_base+2}/7] Training LSTM {h_key} (Optuna trials={lstm_optuna_trials})...")
        try:
            lstm_model = LSTMModel(coin, horizon=h_key)
            lstm_meta = lstm_model.train(train_df, feature_cols, target_col, n_optuna_trials=lstm_optuna_trials)
            horizon_result["lstm"] = lstm_meta or {}
        except Exception as e:
            logger.error(f"LSTM {h_key} failed: {e}")
            horizon_result["lstm"] = {"error": str(e)}

        # Optimize ensemble weights on validation split
        logger.info(f"[{step_base+3}/7] Optimizing ensemble weights {h_key}...")
        try:
            ensemble = EnsemblePredictor(coin, horizon_hours=horizon_hours)
            # Inject the just-trained models (only if training succeeded)
            if ag_meta and hasattr(ag_model, 'predictor') and ag_model.predictor:
                ensemble.models["autogluon"] = ag_model
            if xgb_meta and hasattr(xgb_model, 'model') and xgb_model.model:
                ensemble.models["xgboost"] = xgb_model
            if lstm_meta and hasattr(lstm_model, 'model') and lstm_model.model:
                ensemble.models["lstm"] = lstm_model
            optimized = ensemble.optimize_weights(val_df, feature_cols, target_col)
            horizon_result["ensemble_weights"] = optimized
        except Exception as e:
            logger.error(f"Ensemble optimization {h_key} failed: {e}")
            horizon_result["ensemble_weights"] = {"error": str(e)}

        results["horizons"][h_key] = horizon_result

        # Print horizon summary
        logger.info(f"\n  {coin}/{h_key} Results:")
        for model_name in ["autogluon", "xgboost", "lstm"]:
            meta = horizon_result.get(model_name, {})
            if "error" in meta:
                logger.info(f"    {model_name:12s}: ERROR — {meta['error'][:80]}")
            else:
                acc = meta.get("val_accuracy", meta.get("cv_accuracy_mean", "N/A"))
                logger.info(f"    {model_name:12s}: val_acc = {acc}")
        logger.info(f"    {'weights':12s}: {horizon_result.get('ensemble_weights', 'N/A')}")

    elapsed = time.time() - t_start
    results["train_time_seconds"] = round(elapsed)

    logger.info(f"\n{'='*50}")
    logger.info(f"  {coin} COMPLETE — {elapsed/60:.1f} min")
    logger.info(f"  Models saved to: {settings.MODEL_ARTIFACTS_DIR}")
    logger.info(f"{'='*50}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Crypto Sentinel — Multi-Horizon Training Pipeline")
    parser.add_argument("--coins", default=",".join(TRACKED_COINS.keys()),
                        help="Comma-separated coin symbols (default: all)")
    parser.add_argument("--days", type=int, default=TRAINING_WINDOW_DAYS,
                        help="Training window in days (default: 90)")
    parser.add_argument("--horizons", default="1,4,24",
                        help="Comma-separated prediction horizons in hours (default: 1,4,24)")
    parser.add_argument("--ag-time", type=int, default=300,
                        help="AutoGluon time_limit per horizon in seconds (default: 300)")
    parser.add_argument("--xgb-trials", type=int, default=30,
                        help="Optuna trials for XGBoost (default: 30)")
    parser.add_argument("--lstm-trials", type=int, default=15,
                        help="Optuna trials for LSTM (default: 15)")
    parser.add_argument("--skip-historical", action="store_true",
                        help="Skip Binance historical fetch (use existing DB data)")
    args = parser.parse_args()

    coins = [c.strip().upper() for c in args.coins.split(",") if c.strip()]
    horizons = [int(h.strip()) for h in args.horizons.split(",")]
    invalid = [c for c in coins if c not in TRACKED_COINS]
    if invalid:
        logger.error(f"Unknown coins: {invalid}. Valid: {list(TRACKED_COINS.keys())}")
        sys.exit(1)

    engine = get_engine() if not args.skip_historical else None
    all_results = {}
    overall_start = time.time()

    logger.info(f"╔{'═'*58}╗")
    logger.info(f"║  Crypto Sentinel — Multi-Horizon Training Pipeline      ║")
    logger.info(f"╠{'═'*58}╣")
    logger.info(f"║  Coins:    {', '.join(coins):45s}║")
    logger.info(f"║  Horizons: {', '.join(f'{h}h' for h in horizons):45s}║")
    logger.info(f"║  Days:     {args.days:<45d}║")
    logger.info(f"║  AG Time:  {args.ag_time}s  |  XGB: {args.xgb_trials} trials  |  LSTM: {args.lstm_trials} trials{' '*5}║")
    logger.info(f"║  Output:   {settings.MODEL_ARTIFACTS_DIR[:44]:45s}║")
    logger.info(f"╚{'═'*58}╝")

    for coin in coins:
        try:
            result = train_coin(
                coin,
                days=args.days,
                horizons=horizons,
                ag_time_limit=args.ag_time,
                xgb_optuna_trials=args.xgb_trials,
                lstm_optuna_trials=args.lstm_trials,
                engine=engine if not args.skip_historical else None,
            )
            all_results[coin] = result
        except Exception as e:
            logger.error(f"Training failed for {coin}: {e}")
            import traceback
            traceback.print_exc()
            all_results[coin] = {"error": str(e)}

    total_time = time.time() - overall_start

    # Final summary
    logger.info(f"\n{'═'*60}")
    logger.info(f"  TRAINING COMPLETE — {len(coins)} coins × {len(horizons)} horizons")
    logger.info(f"  Total time: {total_time/60:.1f} min")
    logger.info(f"{'═'*60}")

    for coin, res in all_results.items():
        if res and "horizons" in res:
            for h_key, h_res in res["horizons"].items():
                accs = []
                for m in ["autogluon", "xgboost", "lstm"]:
                    meta = h_res.get(m, {})
                    acc = meta.get("val_accuracy", meta.get("cv_accuracy_mean"))
                    if acc:
                        accs.append(f"{m}={acc:.4f}")
                logger.info(f"  {coin}/{h_key}: {' | '.join(accs) if accs else 'FAILED'}")

    # Save overall report
    report_path = os.path.join(settings.MODEL_ARTIFACTS_DIR, "training_report.json")
    with open(report_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info(f"\nFull report saved to: {report_path}")
    logger.info(f"Models directory: {settings.MODEL_ARTIFACTS_DIR}")
    logger.info(f"  → Copy this entire folder to transfer trained models between machines.")


if __name__ == "__main__":
    main()
