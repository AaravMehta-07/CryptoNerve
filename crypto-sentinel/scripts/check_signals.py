import sqlite3
conn = sqlite3.connect("data/crypto_sentinel.db")

print("=== SIGNALS TABLE SCHEMA ===")
for r in conn.execute("PRAGMA table_info(signals)").fetchall():
    print(f"  {r}")

print("\n=== RECENT SIGNALS ===")
sigs = conn.execute("SELECT coin,signal_type,confidence,generated_at FROM signals ORDER BY generated_at DESC LIMIT 10").fetchall()
for s in sigs:
    print(f"  {s}")
print(f"\nTotal signals: {conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0]}")

print("\n=== PREDICTIONS TABLE SCHEMA ===")
for r in conn.execute("PRAGMA table_info(predictions)").fetchall():
    print(f"  {r}")

print("\n=== RECENT PREDICTIONS ===")
preds = conn.execute("SELECT coin,horizon_hours,direction,confidence,model_name,created_at FROM predictions ORDER BY created_at DESC LIMIT 15").fetchall()
for p in preds:
    print(f"  {p}")
print(f"\nTotal predictions: {conn.execute('SELECT COUNT(*) FROM predictions').fetchone()[0]}")
conn.close()
