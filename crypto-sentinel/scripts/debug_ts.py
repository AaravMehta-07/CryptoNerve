import sqlite3
c = sqlite3.connect("data/crypto_sentinel.db")
# Check latest and earliest
latest = c.execute("SELECT coin, window_start FROM sentiment_aggregated ORDER BY window_start DESC LIMIT 1").fetchone()
earliest = c.execute("SELECT coin, window_start FROM sentiment_aggregated ORDER BY window_start ASC LIMIT 1").fetchone()
total = c.execute("SELECT COUNT(*) FROM sentiment_aggregated").fetchone()[0]
btc_cnt = c.execute("SELECT COUNT(*) FROM sentiment_aggregated WHERE coin='BTC'").fetchone()[0]

from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(timezone.utc) - timedelta(hours=72)).strftime('%Y-%m-%d %H:%M:%S')

# The problem: my script used datetime.utcnow() (local-ish) but time_ago uses timezone.utc
# They might differ. Let me check
print(f"Latest: {latest}")
print(f"Earliest: {earliest}")
print(f"Total: {total}")
print(f"BTC rows: {btc_cnt}")
print(f"API cutoff (72h): {cutoff}")

# Test the exact API query
matched = c.execute("""
    SELECT COUNT(*) FROM sentiment_aggregated
    WHERE coin='BTC' AND window_size='1h' AND window_start>=?
""", (cutoff,)).fetchone()[0]
print(f"Matched with cutoff: {matched}")

# Try without cutoff
all_btc = c.execute("""
    SELECT COUNT(*) FROM sentiment_aggregated
    WHERE coin='BTC' AND window_size='1h'
""").fetchone()[0]
print(f"All BTC 1h (no cutoff): {all_btc}")

c.close()
