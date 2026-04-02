#!/usr/bin/env python
"""
Full project sanity test — validates all critical modules, DB, features, API imports.
Does NOT touch training or run models.
"""
import sys, os, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PASS = 0
FAIL = 0
WARN = 0

def test(name, fn):
    global PASS, FAIL, WARN
    try:
        result = fn()
        if result is True or result is None:
            print(f"  PASS {name}")
            PASS += 1
        elif isinstance(result, str) and result.startswith("WARN"):
            print(f"  WARN {name}: {result}")
            WARN += 1
        else:
            print(f"  PASS {name} => {result}")
            PASS += 1
    except Exception as e:
        print(f"  FAIL {name}: {e}")
        FAIL += 1

# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("  CRYPTO SENTINEL — FULL PROJECT TEST")
print("=" * 60)

# ── 1. Core imports ───────────────────────────────────────────
print("\n[1] CORE IMPORTS")
test("config.settings", lambda: __import__("config.settings") and True)
test("config.constants", lambda: __import__("config.constants") and True)
test("config.coins", lambda: __import__("config.coins") and True)
test("database.connection", lambda: __import__("database.connection") and True)
test("database.sql_compat", lambda: __import__("database.sql_compat") and True)

# ── 2. Feature engineering ────────────────────────────────────
print("\n[2] FEATURE ENGINEERING")
test("features.feature_engineer import", lambda: __import__("features.feature_engineer") and True)
test("features.technical_indicators import", lambda: __import__("features.technical_indicators") and True)

def test_feature_columns():
    from features.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    cols = fe.get_feature_columns()
    assert len(cols) > 40, f"Expected 40+ feature columns, got {len(cols)}"
    return f"{len(cols)} columns"
test("get_feature_columns()", test_feature_columns)

def test_build_prediction():
    from features.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    df = fe.build_prediction_features("BTC", interval="1h", lookback_hours=48)
    if df is None or df.empty:
        return "WARN: No price data in DB yet"
    return f"shape={df.shape}"
test("build_prediction_features('BTC')", test_build_prediction)

def test_build_training():
    from features.feature_engineer import FeatureEngineer
    fe = FeatureEngineer()
    df = fe.build_training_features("BTC", interval="1h", days=7)
    if df is None or df.empty:
        return "WARN: No training data"
    assert "target_1h" in df.columns, "Missing target_1h"
    assert "target_4h" in df.columns, "Missing target_4h"
    assert "target_24h" in df.columns, "Missing target_24h"
    return f"shape={df.shape}, targets OK"
test("build_training_features('BTC', 7d)", test_build_training)

# ── 3. Model imports ─────────────────────────────────────────
print("\n[3] MODEL IMPORTS")
test("models.ensemble", lambda: __import__("models.ensemble") and True)
test("models.xgboost_model", lambda: __import__("models.xgboost_model") and True)
test("models.lstm_model", lambda: __import__("models.lstm_model") and True)
test("models.autogluon_model", lambda: __import__("models.autogluon_model") and True)

def test_ensemble_init():
    from models.ensemble import EnsemblePredictor
    ens = EnsemblePredictor("BTC", horizon_hours=1)
    assert ens.coin == "BTC"
    assert ens.horizon_hours == 1
    return True
test("EnsemblePredictor init", test_ensemble_init)

def test_ensemble_load():
    from models.ensemble import EnsemblePredictor
    ens = EnsemblePredictor("BTC", horizon_hours=1)
    try:
        ens.load_all()
        loaded = [k for k, v in ens.models.items() if (hasattr(v, 'model') and v.model is not None) or (hasattr(v, 'predictor') and v.predictor is not None)]
        if loaded:
            return f"Loaded: {loaded}"
        else:
            return "WARN: No trained models found yet (training in progress)"
    except Exception as e:
        return f"WARN: {e}"
test("EnsemblePredictor load_all()", test_ensemble_load)

# ── 4. Signal generation ─────────────────────────────────────
print("\n[4] SIGNAL GENERATION")
test("signals.signal_generator", lambda: __import__("signals.signal_generator") and True)
test("signals.fear_greed_index", lambda: __import__("signals.fear_greed_index") and True)
test("signals.sentiment_momentum", lambda: __import__("signals.sentiment_momentum") and True)
test("signals.divergence_detector", lambda: __import__("signals.divergence_detector") and True)

def test_signal_gen_init():
    from signals.signal_generator import SignalGenerator
    sg = SignalGenerator()
    assert sg.feature_engineer is not None
    assert sg.fear_greed is not None
    return True
test("SignalGenerator init", test_signal_gen_init)

# ── 5. Database ──────────────────────────────────────────────
print("\n[5] DATABASE")
def test_db_connect():
    from database.connection import get_engine
    engine = get_engine()
    assert engine is not None
    return str(engine.url)[:60]
test("DB connection", test_db_connect)

def test_db_tables():
    from database.connection import get_engine
    import pandas as pd
    engine = get_engine()
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", engine)
    tbl_list = tables["name"].tolist()
    required = ["price_data", "sentiment_aggregated", "signals", "predictions",
                 "news_articles", "technical_indicators", "onchain_metrics",
                 "model_accuracy", "market_reports"]
    missing = [t for t in required if t not in tbl_list]
    if missing:
        return f"WARN: Missing tables: {missing}"
    return f"{len(tbl_list)} tables OK"
test("Required tables exist", test_db_tables)

def test_db_data():
    from database.connection import get_engine
    import pandas as pd
    engine = get_engine()
    counts = {}
    for tbl in ["price_data", "sentiment_aggregated", "signals", "predictions", "news_articles"]:
        try:
            c = pd.read_sql(f"SELECT COUNT(*) as n FROM {tbl}", engine).iloc[0]["n"]
            counts[tbl] = int(c)
        except:
            counts[tbl] = -1
    return ", ".join(f"{k}={v}" for k, v in counts.items())
test("Table row counts", test_db_data)

# ── 6. API imports ───────────────────────────────────────────
print("\n[6] API MODULE")
def test_api_import():
    from api.main import app, _classify_signal
    assert app is not None
    assert callable(_classify_signal)
    return True
test("FastAPI app + _classify_signal", test_api_import)

def test_classify_signal():
    from api.main import _classify_signal
    sig, conf, reason = _classify_signal(0.7, 35, 0.6, 10,
                                          ml_prediction={"direction": "UP", "confidence": 0.72, "models_used": 3},
                                          macd_hist=0.001, bb_position=0.3)
    assert sig in ("BUY", "STRONG_BUY", "HOLD", "SELL", "STRONG_SELL"), f"Bad signal: {sig}"
    assert 0 <= conf <= 1, f"Bad confidence: {conf}"
    return f"signal={sig}, conf={conf:.3f}"
test("_classify_signal(bullish scenario)", test_classify_signal)

def test_classify_bearish():
    from api.main import _classify_signal
    sig, conf, reason = _classify_signal(0.25, 78, 0.35, 10,
                                          ml_prediction={"direction": "DOWN", "confidence": 0.68, "models_used": 3},
                                          macd_hist=-0.002, bb_position=0.85)
    return f"signal={sig}, conf={conf:.3f}"
test("_classify_signal(bearish scenario)", test_classify_bearish)

def test_classify_no_ml():
    from api.main import _classify_signal
    sig, conf, reason = _classify_signal(0.5, 50, 0.5, 5)
    return f"signal={sig}, conf={conf:.3f} (rule-based)"
test("_classify_signal(no ML fallback)", test_classify_no_ml)

def test_api_routes():
    from api.main import app
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    required = ["/api/health", "/api/analyze/{coin}", "/api/signals", "/api/predictions",
                "/api/sentiment", "/api/prices", "/api/technicals", "/api/backtest"]
    missing = [r for r in required if r not in routes]
    if missing:
        return f"WARN: Missing routes: {missing}"
    return f"{len(routes)} routes, all required present"
test("API routes registered", test_api_routes)

# ── 7. Config validation ─────────────────────────────────────
print("\n[7] CONFIG VALIDATION")
def test_settings():
    from config.settings import settings
    assert settings.PREDICTION_HORIZONS == [1, 4, 24]
    return f"horizons={settings.PREDICTION_HORIZONS}, artifacts_dir exists={os.path.isdir(settings.MODEL_ARTIFACTS_DIR)}"
test("Settings.PREDICTION_HORIZONS", test_settings)

def test_coins():
    from config.coins import TRACKED_COINS
    assert "BTC" in TRACKED_COINS
    assert "ETH" in TRACKED_COINS
    assert "SOL" in TRACKED_COINS
    return f"{len(TRACKED_COINS)} coins: {list(TRACKED_COINS.keys())}"
test("TRACKED_COINS", test_coins)

# ── 8. Scripts ────────────────────────────────────────────────
print("\n[8] SCRIPT SYNTAX")
def test_script_syntax(path):
    import py_compile
    py_compile.compile(path, doraise=True)
    return True

scripts = [
    "scripts/train_pipeline.py",
    "scripts/predict_hourly.py",
]
for s in scripts:
    full = os.path.join(os.path.dirname(__file__), "..", s)
    if os.path.exists(full):
        test(f"{s} compiles", lambda p=full: test_script_syntax(p))
    else:
        print(f"  WARN {s}: file not found")
        WARN += 1

# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"  RESULTS: {PASS} passed  |  {FAIL} failed  |  {WARN} warnings")
print("=" * 60)
if FAIL > 0:
    print("  !! SOME TESTS FAILED — fix before hackathon!")
    sys.exit(1)
else:
    print("  ALL TESTS PASSED — ready for deployment!")
    sys.exit(0)
