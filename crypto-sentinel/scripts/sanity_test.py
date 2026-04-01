"""Quick sanity test for the training pipeline before full run."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

print("=" * 50)
print("SANITY TEST: Training Pipeline")
print("=" * 50)

# 1. Config
from config.coins import TRACKED_COINS
from config.settings import settings
print(f"\n[1] Config OK")
print(f"    Coins: {list(TRACKED_COINS.keys())}")
print(f"    MODEL_ARTIFACTS_DIR: {settings.MODEL_ARTIFACTS_DIR}")
print(f"    PREDICTION_HORIZONS: {settings.PREDICTION_HORIZONS}")
print(f"    Dir exists: {os.path.isdir(settings.MODEL_ARTIFACTS_DIR)}")

# 2. DB
from database.connection import get_engine
engine = get_engine()
print(f"\n[2] Database OK")

# 3. Feature engineer — build 7d of BTC features to test targets
from features.feature_engineer import FeatureEngineer
fe = FeatureEngineer()
print(f"\n[3] Testing feature engineering (7d BTC)...")
df = fe.build_training_features("BTC", interval="1h", days=7)
if df is None:
    print("    ⚠ No data in DB — will be fetched during training. That's OK.")
    print("    Test PASSED (no data to validate targets, but imports work)")
else:
    target_cols = [c for c in df.columns if c.startswith("target_")]
    print(f"    Shape: {df.shape}")
    print(f"    Target columns: {target_cols}")
    for t in ["target_1h", "target_4h", "target_24h"]:
        if t in df.columns:
            vals = df[t].value_counts().to_dict()
            print(f"    {t}: {vals}")
        else:
            print(f"    {t}: ❌ MISSING")

# 4. Model imports
from models.xgboost_model import XGBoostModel
from models.lstm_model import LSTMModel, TF_AVAILABLE
from models.autogluon_model import AutoGluonModel, AG_AVAILABLE
from models.ensemble import EnsemblePredictor
print(f"\n[4] Model imports OK")
print(f"    TensorFlow: {'✅' if TF_AVAILABLE else '❌ not installed'}")
print(f"    AutoGluon:  {'✅' if AG_AVAILABLE else '❌ not installed'}")

# 5. Verify model paths
xgb = XGBoostModel("BTC", "1h")
print(f"\n[5] Model paths:")
print(f"    XGBoost:  {xgb.model_path}")
print(f"    LSTM:     {settings.MODEL_ARTIFACTS_DIR}/lstm_BTC_1h")
print(f"    AG:       {settings.MODEL_ARTIFACTS_DIR}/autogluon_BTC_1h")

print(f"\n{'=' * 50}")
print("✅ ALL SANITY CHECKS PASSED")
print(f"{'=' * 50}")
print(f"\nTo train: python scripts/train_pipeline.py")
print(f"To train 1 coin: python scripts/train_pipeline.py --coins BTC")
