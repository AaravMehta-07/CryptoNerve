import sqlite3
from datetime import datetime, timedelta
c = sqlite3.connect("data/crypto_sentinel.db")

print("=== Raw sentiment_aggregated data ===")
r = c.execute("SELECT coin, window_start, avg_sentiment FROM sentiment_aggregated WHERE coin='BTC' ORDER BY window_start DESC LIMIT 5").fetchall()
for x in r:
    print(f"  {x}")

total = c.execute("SELECT COUNT(*) FROM sentiment_aggregated WHERE coin='BTC'").fetchone()[0]
print(f"\nTotal BTC rows: {total}")

# Check what the API cutoff would be
cutoff = (datetime.utcnow() - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%S")
print(f"\nAPI cutoff (72h): {cutoff}")

# Check with the API's exact query
r2 = c.execute("""
    SELECT window_start, avg_sentiment, bullish_count, bearish_count, 
           neutral_count, total_posts
    FROM sentiment_aggregated
    WHERE coin='BTC' AND window_size='1h' AND window_start>=?
    ORDER BY window_start ASC
""", (cutoff,)).fetchall()
print(f"Rows matching API query: {len(r2)}")
if r2:
    print(f"First: {r2[0]}")
    print(f"Last:  {r2[-1]}")

# Also check the format stored
first = c.execute("SELECT window_start FROM sentiment_aggregated LIMIT 1").fetchone()
print(f"\nStored format sample: '{first[0]}'")
print(f"Cutoff format:       '{cutoff}'")
c.close()
