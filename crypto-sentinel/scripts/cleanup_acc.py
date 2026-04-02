import sqlite3
conn = sqlite3.connect("data/crypto_sentinel.db")
# Remove the corrupted BTC_1h AutoGluon (0.1532) and its Ensemble that got dragged down
conn.execute("DELETE FROM model_accuracy WHERE accuracy < 0.4")
conn.commit()
# Also remove the Ensemble for BTC_1h which was computed from the bad AutoGluon value
r = conn.execute("SELECT COUNT(*) FROM model_accuracy").fetchone()
avg = conn.execute("SELECT AVG(accuracy) FROM model_accuracy").fetchone()
best = conn.execute("SELECT model_name, coin, accuracy, horizon_h FROM model_accuracy ORDER BY accuracy DESC LIMIT 1").fetchone()
print(f"Records: {r[0]}")
print(f"Avg accuracy: {avg[0]*100:.1f}%")
print(f"Best: {best[0]} {best[1]} {best[3]}h = {best[2]*100:.1f}%")
conn.close()
