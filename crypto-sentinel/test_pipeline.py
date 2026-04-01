"""
Quick end-to-end test:
  1. Test Ollama connection
  2. Fetch real news from RSS + NewsAPI + CryptoPanic
  3. Score 3 articles through Ollama
  4. Print results
"""
import json, os, sys, urllib.request, re, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
CRYPTOPANIC_TOKEN = os.environ.get("CRYPTOPANIC_API_TOKEN", "")

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ── 1. TEST OLLAMA CONNECTION ─────────────────────────────────────────────
section("1. OLLAMA CONNECTION TEST")
try:
    req = urllib.request.Request(f"{OLLAMA_URL}/api/tags",
                                headers={"User-Agent": "TestScript/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
    models = [m.get("name", "") for m in data.get("models", [])]
    print(f"  ✅ Ollama is running at {OLLAMA_URL}")
    print(f"  📦 Available models: {models}")
    found = any(OLLAMA_MODEL in m for m in models)
    if found:
        print(f"  ✅ Target model '{OLLAMA_MODEL}' found")
    else:
        print(f"  ❌ Target model '{OLLAMA_MODEL}' NOT found")
        sys.exit(1)
except Exception as e:
    print(f"  ❌ Ollama not reachable: {e}")
    sys.exit(1)

# ── 2. QUICK LLM INFERENCE TEST ──────────────────────────────────────────
section("2. OLLAMA INFERENCE TEST (single headline)")
test_headline = "Bitcoin surges past $95,000 as ETF inflows hit record $2.3 billion"
prompt = (
    f'[INST] You are a crypto sentiment analyst. Analyze this headline and return ONLY JSON.\n'
    f'TEXT: "{test_headline}"\n'
    f'Output: {{"label":"BULLISH|BEARISH|NEUTRAL|FUD","score":0.0_to_1.0,"confidence":0.0_to_1.0,"reasoning":"one sentence"}} [/INST]'
)
try:
    payload = json.dumps({
        "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1, "num_predict": 150},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    print(f"  ⏳ Sending to Ollama (may take 10-30s on CPU)...")
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    raw = resp.get("response", "")
    print(f"  📝 Raw LLM output: {raw[:200]}")
    m = re.search(r'\{.*?\}', raw, re.DOTALL)
    if m:
        parsed = json.loads(m.group())
        print(f"  ✅ Parsed JSON: {json.dumps(parsed, indent=4)}")
    else:
        print(f"  ⚠️  Could not extract JSON from response")
    print(f"  ⏱️  Eval time: {resp.get('total_duration', 0)/1e9:.1f}s")
except Exception as e:
    print(f"  ❌ Inference failed: {e}")

# ── 3. FETCH NEWS FROM RSS ────────────────────────────────────────────────
section("3. RSS NEWS FETCH")
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://cryptobriefing.com/feed/",
    "https://decrypt.co/feed",
]
all_articles = []
for feed_url in RSS_FEEDS:
    try:
        req = urllib.request.Request(feed_url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw_xml = r.read()
        root = ET.fromstring(raw_xml)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if title:
                items.append({"title": title, "source": feed_url.split("/")[2]})
        all_articles.extend(items)
        print(f"  ✅ {feed_url.split('/')[2]}: {len(items)} articles")
    except Exception as e:
        print(f"  ❌ {feed_url.split('/')[2]}: {e}")

# ── 4. FETCH FROM NEWSAPI ────────────────────────────────────────────────
section("4. NEWSAPI FETCH")
if NEWS_API_KEY:
    try:
        url = f"https://newsapi.org/v2/everything?q=bitcoin+crypto&language=en&sortBy=publishedAt&pageSize=10&apiKey={NEWS_API_KEY}"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        newsapi_arts = [{"title": a["title"], "source": "NewsAPI"} for a in data.get("articles", []) if a.get("title")]
        all_articles.extend(newsapi_arts)
        print(f"  ✅ NewsAPI: {len(newsapi_arts)} articles fetched")
    except Exception as e:
        print(f"  ❌ NewsAPI: {e}")
else:
    print(f"  ⚠️  NEWS_API_KEY not set, skipping")

# ── 5. FETCH FROM CRYPTOPANIC ────────────────────────────────────────────
section("5. CRYPTOPANIC FETCH")
if CRYPTOPANIC_TOKEN:
    try:
        url = f"https://cryptopanic.com/api/free/v1/posts/?auth_token={CRYPTOPANIC_TOKEN}&currencies=BTC&kind=news&public=true"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        cp_arts = [{"title": p["title"], "source": "CryptoPanic"} for p in data.get("results", [])[:10] if p.get("title")]
        all_articles.extend(cp_arts)
        print(f"  ✅ CryptoPanic: {len(cp_arts)} articles fetched")
    except Exception as e:
        print(f"  ❌ CryptoPanic: {e}")
else:
    print(f"  ⚠️  CRYPTOPANIC_API_TOKEN not set, skipping")

# ── 6. Filter for BTC-relevant articles ──────────────────────────────────
btc_keywords = ["bitcoin", "btc", "halving", "satoshi", "crypto", "etf"]
btc_articles = [a for a in all_articles if any(kw in a["title"].lower() for kw in btc_keywords)]
print(f"\n  📊 Total articles: {len(all_articles)}, BTC-relevant: {len(btc_articles)}")

# ── 7. ANALYZE TOP 3 ARTICLES THROUGH OLLAMA ─────────────────────────────
section("6. LLM SENTIMENT ANALYSIS (3 articles via Ollama)")
to_analyze = btc_articles[:3] if btc_articles else all_articles[:3]
for i, art in enumerate(to_analyze):
    print(f"\n  [{i+1}/3] \"{art['title'][:80]}...\"")
    print(f"         Source: {art['source']}")
    prompt = (
        f'[INST] You are a crypto sentiment analyst for BTC.\n'
        f'Analyze: "{art["title"][:500]}"\n'
        f'Return ONLY: {{"label":"BULLISH|BEARISH|NEUTRAL|FUD","score":0.0_to_1.0,"confidence":0.0_to_1.0,"reasoning":"one sentence"}} [/INST]'
    )
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_predict": 150, "stop": ["[INST]"]},
        }).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=payload,
                                    headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
        raw = resp.get("response", "")
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            label = parsed.get("label", "?")
            score = parsed.get("score", "?")
            conf = parsed.get("confidence", "?")
            reason = parsed.get("reasoning", "")
            print(f"         ✅ {label} | score={score} | conf={conf}")
            print(f"         💬 {reason}")
        else:
            print(f"         ⚠️  No JSON in response: {raw[:100]}")
        print(f"         ⏱️  {resp.get('total_duration',0)/1e9:.1f}s")
    except Exception as e:
        print(f"         ❌ Error: {e}")

section("DONE")
print(f"  Pipeline test complete. Ollama is working ✅")
print(f"  Total news sources: RSS({len(RSS_FEEDS)}) + NewsAPI + CryptoPanic")
print(f"  Articles found: {len(all_articles)} total, {len(btc_articles)} BTC-relevant")
