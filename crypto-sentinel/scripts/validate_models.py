"""
scripts/validate_models.py — Validate trained models load & predict correctly.
Does NOT train anything. Read-only test of the full pipeline.

Usage: python scripts/validate_models.py
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.ensemble import EnsemblePredictor
from features.feature_engineer import FeatureEngineer
import numpy as np

COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
HORIZONS = [1, 4, 24]
MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")

passed = 0
failed = 0
warnings = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  ✅ {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  ❌ {msg}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  ⚠️  {msg}")

print("="*70)
print("  CRYPTO SENTINEL — MODEL VALIDATION")
print("="*70)

# ── 1. Check all model files exist ───────────────────────────────────────────
print("\n📁 [1/5] Checking model files exist...")
for coin in COINS:
    for h in HORIZONS:
        tag = f"{coin}_{h}h"
        # AutoGluon
        ag_dir = os.path.join(MODEL_DIR, f"autogluon_{tag}")
        if os.path.isdir(ag_dir) and len(os.listdir(ag_dir)) > 0:
            ok(f"AutoGluon {tag}: {len(os.listdir(ag_dir))} files")
        else:
            fail(f"AutoGluon {tag}: MISSING or empty")

        # XGBoost
        xgb_file = os.path.join(MODEL_DIR, f"xgboost_{tag}.json")
        xgb_meta = os.path.join(MODEL_DIR, f"xgboost_{tag}_meta.json")
        if os.path.exists(xgb_file) and os.path.exists(xgb_meta):
            ok(f"XGBoost {tag}: model + meta present ({os.path.getsize(xgb_file):,} bytes)")
        else:
            fail(f"XGBoost {tag}: MISSING model or meta")

        # LSTM
        lstm_dir = os.path.join(MODEL_DIR, f"lstm_{tag}")
        lstm_scaler = os.path.join(MODEL_DIR, f"lstm_{tag}_scaler.json")
        if os.path.isdir(lstm_dir) and os.path.exists(lstm_scaler):
            ok(f"LSTM {tag}: model dir + scaler present")
        else:
            fail(f"LSTM {tag}: MISSING model dir or scaler")

        # Ensemble weights
        ew_file = os.path.join(MODEL_DIR, f"ensemble_weights_{tag}.json")
        if os.path.exists(ew_file):
            with open(ew_file) as f:
                w = json.load(f)
            wsum = sum(w.values())
            if 0.95 <= wsum <= 1.05:
                ok(f"Ensemble weights {tag}: {w} (sum={wsum:.3f})")
            else:
                warn(f"Ensemble weights {tag}: sum={wsum:.3f} (expected ~1.0)")
        else:
            fail(f"Ensemble weights {tag}: MISSING")

# ── 2. Test model loading via EnsemblePredictor ──────────────────────────────
print(f"\n🔄 [2/5] Testing EnsemblePredictor.load_all()...")
loaded = {}
for coin in COINS:
    for h in HORIZONS:
        tag = f"{coin}_{h}h"
        try:
            ens = EnsemblePredictor(coin, horizon_hours=h)
            ens.load_all()
            models_loaded = []
            if hasattr(ens, 'models'):
                for name, model in ens.models.items():
                    if hasattr(model, 'model') and model.model is not None:
                        models_loaded.append(name)
                    elif hasattr(model, 'predictor') and model.predictor is not None:
                        models_loaded.append(name)
            if models_loaded:
                ok(f"{tag}: Loaded {len(models_loaded)} models: {models_loaded}")
                loaded[tag] = ens
            else:
                warn(f"{tag}: EnsemblePredictor loaded but no models found in memory")
        except Exception as e:
            fail(f"{tag}: load failed — {e}")

# ── 3. Test feature engineering ──────────────────────────────────────────────
print(f"\n🛠  [3/5] Testing FeatureEngineer...")
fe = FeatureEngineer()
feat_dfs = {}
for coin in COINS:
    try:
        df = fe.build_prediction_features(coin, interval="1h", lookback_hours=72)
        if df is not None and len(df) > 30:
            feat_cols = [c for c in fe.get_feature_columns() if c in df.columns]
            ok(f"{coin}: {len(df)} rows, {len(feat_cols)} features available")
            feat_dfs[coin] = (df, feat_cols)
        else:
            warn(f"{coin}: {len(df) if df is not None else 0} rows (may not have enough data yet)")
    except Exception as e:
        fail(f"{coin}: feature build failed — {e}")

# ── 4. Test predictions ─────────────────────────────────────────────────────
print(f"\n🔮 [4/5] Testing predictions...")
for coin in COINS:
    if coin not in feat_dfs:
        warn(f"{coin}: Skipped (no features)")
        continue

    df, feat_cols = feat_dfs[coin]
    for h in HORIZONS:
        tag = f"{coin}_{h}h"
        if tag not in loaded:
            warn(f"{tag}: Skipped (not loaded)")
            continue

        ens = loaded[tag]
        try:
            # Get current price from features
            current_price = float(df["close"].iloc[-1]) if "close" in df.columns else 0
            pred = ens.predict(df[feat_cols], current_price=current_price)
            if pred and "direction" in pred and "confidence" in pred:
                d = pred["direction"]
                c = pred["confidence"]
                m = pred.get("models_used", "?")
                ok(f"{tag}: {d} @ {c:.1%} confidence ({m} models)")
            else:
                fail(f"{tag}: predict returned invalid format: {pred}")
        except Exception as e:
            fail(f"{tag}: predict failed — {e}")
            traceback.print_exc()

# ── 5. Test API integration ──────────────────────────────────────────────────
print(f"\n🌐 [5/5] Testing API server connectivity...")
import urllib.request
try:
    with urllib.request.urlopen("http://localhost:8000/api/health", timeout=5) as r:
        data = json.loads(r.read())
        ok(f"API healthy: {data}")
except Exception as e:
    warn(f"API server not reachable (run: uvicorn api.main:app --port 8000): {e}")

# Test key endpoints
endpoints = [
    "/api/signals/latest",
    "/api/fear-greed?hours=48",
    "/api/sentiment/heatmap?hours=12",
    "/api/technicals?coin=BTC&hours=48",
    "/api/onchain?coin=BTC&hours=168",
    "/api/predictions?horizon=1",
    "/api/model-accuracy",
    "/api/news?hours=72&limit=5",
]
for ep in endpoints:
    try:
        with urllib.request.urlopen(f"http://localhost:8000{ep}", timeout=5) as r:
            data = json.loads(r.read())
            count = len(data) if isinstance(data, list) else "obj"
            ok(f"{ep.split('?')[0]}: {count} records")
    except Exception as e:
        warn(f"{ep.split('?')[0]}: {e}")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print(f"  RESULTS:  ✅ {passed} passed  |  ❌ {failed} failed  |  ⚠️  {warnings} warnings")
print("="*70)

if failed == 0:
    print("  🎉 ALL MODELS VALIDATED — READY FOR HACKATHON DEMO")
else:
    print(f"  ⚠️  {failed} issues need attention before demo")
print()
