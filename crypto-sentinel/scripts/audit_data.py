"""Quick audit: what's real vs fabricated in model_accuracy + prediction coverage."""
import sqlite3, os, json, glob

db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "crypto_sentinel.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

print("=" * 70)
print("  1. MODEL ACCURACY TABLE — What's displayed on Performance page")
print("=" * 70)
rows = conn.execute("SELECT coin, model_name, accuracy, precision, recall, f1_score, sharpe FROM model_accuracy ORDER BY accuracy DESC").fetchall()
for r in rows:
    print(f"  {r['coin']:5s} {r['model_name']:15s} acc={r['accuracy']:.4f}  prec={r['precision']:.4f}  rec={r['recall']:.4f}  f1={r['f1_score']:.4f}  sharpe={r['sharpe']:.4f}")

# Average
accs = [r['accuracy'] for r in rows]
print(f"\n  AVG accuracy across all: {sum(accs)/len(accs)*100:.1f}%  ({len(accs)} records)")

print("\n" + "=" * 70)
print("  2. REAL XGBoost ACCURACY from trained model meta.json files")
print("=" * 70)
model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trained_models")
for meta_file in sorted(glob.glob(os.path.join(model_dir, "xgboost_*_meta.json"))):
    with open(meta_file) as f:
        meta = json.load(f)
    tag = os.path.basename(meta_file).replace("xgboost_", "").replace("_meta.json", "")
    acc = meta.get("test_accuracy") or meta.get("accuracy") or meta.get("val_accuracy", "N/A")
    print(f"  {tag:12s} real XGB accuracy = {acc}")

# Check for AutoGluon and LSTM meta files
print("\n  AutoGluon meta files:")
ag_metas = glob.glob(os.path.join(model_dir, "autogluon_*/meta.json")) + glob.glob(os.path.join(model_dir, "autogluon_*_meta.json"))
if ag_metas:
    for f in sorted(ag_metas):
        print(f"    Found: {os.path.basename(f)}")
else:
    print("    NONE — no real AutoGluon accuracy data available")

print("\n  LSTM meta/scaler files:")
lstm_metas = glob.glob(os.path.join(model_dir, "lstm_*_scaler.json"))
for f in sorted(lstm_metas)[:3]:
    with open(f) as fh:
        data = json.load(fh)
    tag = os.path.basename(f).replace("lstm_", "").replace("_scaler.json", "")
    has_acc = "accuracy" in data or "test_accuracy" in data
    print(f"    {tag}: keys={list(data.keys())[:5]} has_accuracy={has_acc}")

print("\n" + "=" * 70)
print("  3. PREDICTIONS BY HORIZON")
print("=" * 70)
for h in [1, 4, 24]:
    preds = conn.execute("""
        SELECT coin, COUNT(*) cnt,
               SUM(CASE WHEN was_correct=1 THEN 1 ELSE 0 END) wins,
               SUM(CASE WHEN was_correct=0 THEN 1 ELSE 0 END) losses,
               SUM(CASE WHEN was_correct IS NULL THEN 1 ELSE 0 END) pending
        FROM predictions WHERE horizon_hours=? GROUP BY coin
    """, (h,)).fetchall()
    print(f"\n  Horizon {h}h:")
    if preds:
        for p in preds:
            print(f"    {p['coin']:5s} total={p['cnt']} wins={p['wins']} losses={p['losses']} pending={p['pending']}")
    else:
        print("    NO PREDICTIONS")

total = conn.execute("SELECT COUNT(*) c FROM predictions").fetchone()['c']
print(f"\n  Total predictions in DB: {total}")

print("\n" + "=" * 70)
print("  4. VERDICT")
print("=" * 70)
print("""
  MODEL ACCURACY:
    - XGBoost: REAL from trained model meta.json (0.48-0.70 range)
    - AutoGluon_Ens, LSTM_v2, Ensemble: ESTIMATED base stats
      (hardcoded in populate_live_data.py, NOT from actual training)
    - The 62.6% avg and 79% Ensemble are ESTIMATED, not measured

  TO FIX: Replace with ONLY real data from actual model evaluations
""")

conn.close()
