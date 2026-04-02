"""Inspect all available metrics from trained model meta files."""
import os, json, glob

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")

# XGBoost meta — full keys
print("=== XGBOOST META (BTC_1h sample) ===")
with open(os.path.join(MODEL_DIR, "xgboost_BTC_1h_meta.json")) as f:
    data = json.load(f)
for k, v in data.items():
    print(f"  {k}: {v}")

print("\n=== LSTM SCALER (BTC_1h sample) ===")
with open(os.path.join(MODEL_DIR, "lstm_BTC_1h_scaler.json")) as f:
    data = json.load(f)
for k, v in data.items():
    if k == 'scaler_params':
        print(f"  {k}: [mean/scale arrays - {len(v.get('mean',[]))} features]")
    elif k == 'features':
        print(f"  {k}: [{len(v)} features]")
    elif k == 'best_params':
        print(f"  {k}: {v}")
    else:
        print(f"  {k}: {v}")

print("\n=== AUTOGLUON META (BTC_1h sample) ===")
ag_meta = os.path.join(MODEL_DIR, "autogluon_BTC_1h", "meta.json")
if os.path.exists(ag_meta):
    with open(ag_meta) as f:
        data = json.load(f)
    for k, v in data.items():
        print(f"  {k}: {v}")

# Check for AutoGluon leaderboard or evaluation files
print("\n=== AUTOGLUON DIR CONTENTS (BTC_1h) ===")
ag_dir = os.path.join(MODEL_DIR, "autogluon_BTC_1h")
for item in os.listdir(ag_dir):
    full = os.path.join(ag_dir, item)
    if os.path.isfile(full):
        print(f"  FILE: {item} ({os.path.getsize(full)} bytes)")
    else:
        print(f"  DIR:  {item}/")

# Check all XGB metas for available metrics
print("\n=== ALL XGBOOST METRICS ===")
for f in sorted(glob.glob(os.path.join(MODEL_DIR, "xgboost_*_meta.json"))):
    with open(f) as fh:
        d = json.load(fh)
    tag = os.path.basename(f).replace("xgboost_", "").replace("_meta.json", "")
    acc = d.get("test_accuracy", "?")
    prec = d.get("test_precision", d.get("precision", "?"))
    rec = d.get("test_recall", d.get("recall", "?"))
    f1 = d.get("test_f1", d.get("f1", d.get("f1_score", "?")))
    print(f"  {tag:12s} acc={acc}  prec={prec}  rec={rec}  f1={f1}")
