"""Check real model accuracy from all trained model files + prediction coverage."""
import sqlite3, os, json, glob

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")

# 1. Check LSTM val_accuracy
print("=== LSTM val_accuracy from scaler files ===")
for f in sorted(glob.glob(os.path.join(MODEL_DIR, "lstm_*_scaler.json"))):
    with open(f) as fh:
        data = json.load(fh)
    tag = os.path.basename(f).replace("lstm_", "").replace("_scaler.json", "")
    val_acc = data.get("val_accuracy", "N/A")
    print(f"  {tag:12s} val_accuracy = {val_acc}")

# 2. Check AutoGluon accuracy
print("\n=== AutoGluon accuracy from meta files ===")
for d in sorted(glob.glob(os.path.join(MODEL_DIR, "autogluon_*"))):
    if not os.path.isdir(d): continue
    tag = os.path.basename(d).replace("autogluon_", "")
    meta_path = os.path.join(d, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as fh:
            data = json.load(fh)
        acc = data.get("test_accuracy") or data.get("accuracy") or data.get("val_accuracy") or data.get("score")
        keys = [k for k in data.keys() if 'acc' in k.lower() or 'score' in k.lower() or 'metric' in k.lower()]
        print(f"  {tag:12s} accuracy={acc}  relevant_keys={keys}")
        if not acc:
            print(f"             all_keys={list(data.keys())[:10]}")

# 3. Check predictions
print("\n=== PREDICTIONS IN DB ===")
db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "crypto_sentinel.db")
conn = sqlite3.connect(db)
for h in [1, 4, 24]:
    rows = conn.execute(f"SELECT coin, model_name, predicted_direction, confidence, was_correct FROM predictions WHERE horizon_hours={h}").fetchall()
    print(f"\n  Horizon {h}h: {len(rows)} predictions")
    for r in rows:
        print(f"    {r[0]:5s} model={r[1]:20s} dir={r[2]:5s} conf={r[3]:.2f}  correct={r[4]}")

total = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
print(f"\n  TOTAL: {total} predictions across all horizons")
conn.close()
