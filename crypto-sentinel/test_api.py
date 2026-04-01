"""Quick diagnostic: test each component of the analyze pipeline."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

print("=== Test 1: DB ===")
try:
    from database.connection import get_engine
    from sqlalchemy import text
    eng = get_engine()
    with eng.begin() as conn:
        r = conn.execute(text("SELECT COUNT(*) FROM signals")).fetchone()
        print(f"  OK: {r[0]} signals in DB")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n=== Test 2: RSS ===")
try:
    import urllib.request
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        headers={"User-Agent": "CryptoSentinel/2.0"}
    )
    with urllib.request.urlopen(req, timeout=7) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = list(root.iter("item"))
    print(f"  OK: {len(items)} items from CoinDesk")
    if items:
        t = items[0].findtext("title")
        print(f"  First: {t}")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n=== Test 3: GGUF model ===")
model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "models", "mistral-7b-instruct-v0.1.Q3_K_M.gguf")
print(f"  Path: {model_path}")
print(f"  Exists: {os.path.exists(model_path)}")
if os.path.exists(model_path):
    print(f"  Size: {os.path.getsize(model_path) / 1e9:.2f} GB")

print("\n=== Test 4: llama-cpp-python ===")
try:
    from llama_cpp import Llama
    print("  OK: llama_cpp importable")
except ImportError as e:
    print(f"  FAIL: {e}")

print("\n=== Test 5: Binance ===")
try:
    import json
    req = urllib.request.Request(
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
        headers={"User-Agent": "CryptoSentinel/2.0"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    print(f"  OK: BTC=${float(data['price']):,.2f}")
except Exception as e:
    print(f"  FAIL: {e}")

print("\n=== Test 6: Load api.main module ===")
try:
    import api.main as m
    print(f"  OK: api.main loaded, app={m.app.title}")
    print(f"  LLM model path: {m._MODEL_PATH}")
    print(f"  LLM model exists: {os.path.exists(m._MODEL_PATH)}")
except Exception as e:
    import traceback
    print(f"  FAIL: {e}")
    traceback.print_exc()

print("\n=== Test 7: Try _run_analysis (BTC) ===")
try:
    from api.main import _run_analysis
    eng = get_engine()
    with eng.begin() as conn:
        result = _run_analysis("BTC", conn)
    print(f"  OK: signal={result['signal']}, llm_model={result['llm_model']}")
    print(f"  Articles: {result['articles']}, Sentiment: {result['sentiment']:.3f}")
    print(f"  Reasoning: {result['reasoning'][:200]}")
except Exception as e:
    import traceback
    print(f"  FAIL: {e}")
    traceback.print_exc()
