"""
Direct pipeline test — no API server needed.
Tests: Ollama connection → RSS fetch → NewsAPI fetch → LLM scoring → DB write → read back
Run:  python test_full_pipeline.py
"""
import os, sys, json, time, hashlib, re, urllib.request, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Config ────────────────────────────────────────────────────────────────
OLLAMA_URL   = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
CP_TOKEN     = os.environ.get("CRYPTOPANIC_API_TOKEN", "")

PASS = 0
FAIL = 0

def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

def section(title):
    print(f"\n{'─'*60}\n  {title}\n{'─'*60}")

# ══════════════════════════════════════════════════════════════════════════
# TEST 1: OLLAMA CONNECTION
# ══════════════════════════════════════════════════════════════════════════
section("TEST 1: OLLAMA CONNECTION")
ollama_ok = False
try:
    req = urllib.request.Request(f"{OLLAMA_URL}/api/tags",
                                headers={"User-Agent": "Test/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.loads(r.read())
    models = [m.get("name", "") for m in data.get("models", [])]
    test("Ollama server reachable", True, f"{OLLAMA_URL}")
    found = any(OLLAMA_MODEL in m for m in models)
    test(f"Model '{OLLAMA_MODEL}' available", found, f"Models: {models}")
    ollama_ok = found
except Exception as e:
    test("Ollama server reachable", False, str(e))

# ══════════════════════════════════════════════════════════════════════════
# TEST 2: LLM INFERENCE (single headline)
# ══════════════════════════════════════════════════════════════════════════
section("TEST 2: LLM INFERENCE")
llm_result = None
if ollama_ok:
    headline = "Bitcoin surges past $95,000 as ETF inflows hit $2.3 billion record"
    prompt = (
        f'[INST] You are a crypto sentiment analyst for BTC.\n'
        f'Analyze: "{headline}"\n'
        f'Return ONLY: {{"label":"BULLISH|BEARISH|NEUTRAL|FUD","score":0.0_to_1.0,'
        f'"confidence":0.0_to_1.0,"reasoning":"one sentence"}} [/INST]'
    )
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.1, "num_predict": 150},
        }).encode()
        req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=payload,
                                    headers={"Content-Type": "application/json"}, method="POST")
        print(f"  ⏳ Sending headline to Ollama...")
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
        elapsed = time.time() - t0
        raw = resp.get("response", "")
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        test("LLM returned a response", bool(raw), f"{elapsed:.1f}s")
        if m:
            llm_result = json.loads(m.group())
            test("JSON parsed from response", True, json.dumps(llm_result))
            test("Has 'label' field", "label" in llm_result, llm_result.get("label"))
            test("Has 'score' field (0-1)", "score" in llm_result and 0 <= float(llm_result["score"]) <= 1,
                 str(llm_result.get("score")))
            test("Has 'confidence' field", "confidence" in llm_result, str(llm_result.get("confidence")))
            test("Has 'reasoning' field", "reasoning" in llm_result, llm_result.get("reasoning", "")[:80])
            test("Label is valid sentiment", llm_result.get("label") in ("BULLISH","BEARISH","NEUTRAL","FUD"),
                 llm_result.get("label"))
        else:
            test("JSON parsed from response", False, f"Raw: {raw[:120]}")
    except Exception as e:
        test("LLM inference completed", False, str(e))
else:
    print("  ⏭️  Skipping — Ollama not available")

# ══════════════════════════════════════════════════════════════════════════
# TEST 3: RSS FEED FETCH
# ══════════════════════════════════════════════════════════════════════════
section("TEST 3: RSS FEED FETCH")
RSS_FEEDS = {
    "cointelegraph.com": "https://cointelegraph.com/rss",
    "cryptobriefing.com": "https://cryptobriefing.com/feed/",
    "decrypt.co": "https://decrypt.co/feed",
}
all_articles = []
for name, url in RSS_FEEDS.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw_xml = r.read()
        root = ET.fromstring(raw_xml)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            desc = (item.findtext("description") or "").strip()[:200]
            link = (item.findtext("link") or "").strip()
            if title:
                items.append({"title": title, "description": desc, "link": link, "source": name})
        all_articles.extend(items)
        test(f"RSS {name}", len(items) > 0, f"{len(items)} articles")
    except Exception as e:
        test(f"RSS {name}", False, str(e))

test("Total RSS articles > 0", len(all_articles) > 0, f"{len(all_articles)} total")

# ══════════════════════════════════════════════════════════════════════════
# TEST 4: NEWSAPI FETCH
# ══════════════════════════════════════════════════════════════════════════
section("TEST 4: NEWSAPI FETCH")
newsapi_articles = []
if NEWS_API_KEY:
    try:
        url = (f"https://newsapi.org/v2/everything?q=bitcoin+crypto&language=en"
               f"&sortBy=publishedAt&pageSize=5&apiKey={NEWS_API_KEY}")
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        newsapi_articles = [
            {"title": a["title"], "description": (a.get("description") or "")[:200],
             "link": a.get("url", ""), "source": "NewsAPI"}
            for a in data.get("articles", []) if a.get("title")
        ]
        all_articles.extend(newsapi_articles)
        test("NewsAPI fetch", len(newsapi_articles) > 0, f"{len(newsapi_articles)} articles")
    except Exception as e:
        test("NewsAPI fetch", False, str(e))
else:
    print("  ⚠️  NEWS_API_KEY not set — skipping")

# ══════════════════════════════════════════════════════════════════════════
# TEST 5: CRYPTOPANIC FETCH
# ══════════════════════════════════════════════════════════════════════════
section("TEST 5: CRYPTOPANIC FETCH")
if CP_TOKEN:
    try:
        url = (f"https://cryptopanic.com/api/free/v1/posts/"
               f"?auth_token={CP_TOKEN}&currencies=BTC&kind=news&public=true")
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        cp = [{"title": p["title"], "description": "", "link": p.get("url",""), "source": "CryptoPanic"}
              for p in data.get("results", [])[:5] if p.get("title")]
        all_articles.extend(cp)
        test("CryptoPanic fetch", len(cp) > 0, f"{len(cp)} articles")
    except Exception as e:
        test("CryptoPanic fetch", False, str(e))
else:
    print("  ⚠️  CRYPTOPANIC_API_TOKEN not set — skipping")

# ══════════════════════════════════════════════════════════════════════════
# TEST 6: FILTER BTC-RELEVANT ARTICLES
# ══════════════════════════════════════════════════════════════════════════
section("TEST 6: ARTICLE FILTERING")
btc_kw = ["bitcoin", "btc", "halving", "satoshi", "crypto", "etf", "blockchain"]
btc_articles = [a for a in all_articles if any(kw in a["title"].lower() for kw in btc_kw)]
test("BTC-relevant filter", len(btc_articles) > 0, f"{len(btc_articles)}/{len(all_articles)} matched")

# ══════════════════════════════════════════════════════════════════════════
# TEST 7: SCORE 5 ARTICLES THROUGH OLLAMA
# ══════════════════════════════════════════════════════════════════════════
section("TEST 7: LLM BATCH SCORING (5 articles)")
scored = []
to_score = (btc_articles if btc_articles else all_articles)[:5]

if ollama_ok and to_score:
    for i, art in enumerate(to_score):
        title = art["title"][:80]
        text = (art["title"] + ". " + art.get("description", "")[:200]).strip()
        prompt = (
            f'[INST] You are a crypto sentiment analyst for BTC.\n'
            f'Analyze: "{text[:500]}"\n'
            f'Return ONLY: {{"label":"BULLISH|BEARISH|NEUTRAL|FUD","score":0.0_to_1.0,'
            f'"confidence":0.0_to_1.0,"reasoning":"one sentence"}} [/INST]'
        )
        print(f"  ⏳ [{i+1}/{len(to_score)}] \"{title}...\"")
        try:
            payload = json.dumps({
                "model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 150, "stop": ["[INST]"]},
            }).encode()
            req = urllib.request.Request(f"{OLLAMA_URL}/api/generate", data=payload,
                                        headers={"Content-Type": "application/json"}, method="POST")
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
            elapsed = time.time() - t0
            raw = resp.get("response", "")
            m = re.search(r'\{.*?\}', raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                label = parsed.get("label", "?")
                score = parsed.get("score", "?")
                conf = parsed.get("confidence", "?")
                reason = parsed.get("reasoning", "")[:60]
                scored.append({"title": title, **parsed})
                test(f"Article {i+1} scored", True,
                     f"{label} score={score} conf={conf} ({elapsed:.1f}s) — {reason}")
            else:
                test(f"Article {i+1} scored", False, f"No JSON: {raw[:80]}")
        except Exception as e:
            test(f"Article {i+1} scored", False, str(e))

    test("All 5 articles scored", len(scored) == len(to_score),
         f"{len(scored)}/{len(to_score)}")

    # Stats
    if scored:
        avg_score = sum(s["score"] for s in scored) / len(scored)
        labels = [s["label"] for s in scored]
        print(f"\n  📊 Batch stats:")
        print(f"     Avg score: {avg_score:.3f}")
        print(f"     Labels: {', '.join(labels)}")
        bull = labels.count("BULLISH")
        bear = labels.count("BEARISH") + labels.count("FUD")
        neut = labels.count("NEUTRAL")
        print(f"     Bullish: {bull}  Bearish: {bear}  Neutral: {neut}")
else:
    print("  ⏭️  Skipping — Ollama not available or no articles")

# ══════════════════════════════════════════════════════════════════════════
# TEST 8: DATABASE WRITE + READ
# ══════════════════════════════════════════════════════════════════════════
section("TEST 8: DATABASE WRITE + READBACK")
try:
    from database.connection import get_engine
    from sqlalchemy import text
    engine = get_engine()
    
    with engine.connect() as conn:
        # Write scored articles
        written = 0
        for s in scored:
            aid = hashlib.md5(s["title"].encode()).hexdigest()[:32]
            try:
                conn.execute(text(
                    "INSERT OR IGNORE INTO news_articles "
                    "(article_id,source_name,title,coin,published_at,sentiment_label,sentiment_score) "
                    "VALUES (:aid,:src,:title,:coin,datetime('now'),:lbl,:score)"
                ), {"aid": aid, "src": "test", "title": s["title"][:500],
                    "coin": "BTC", "lbl": s["label"], "score": s["score"]})
                written += 1
            except Exception as e:
                print(f"  ⚠️  Write error: {e}")
        conn.commit()
        test("Articles written to DB", written > 0, f"{written} rows")

        # Read back
        rows = conn.execute(text(
            "SELECT source_name AS source, title, sentiment_label, sentiment_score "
            "FROM news_articles ORDER BY published_at DESC LIMIT 5"
        )).fetchall()
        test("Articles read back from DB", len(rows) > 0, f"{len(rows)} rows")
        for r in rows[:3]:
            print(f"    [{r[2]}] {r[0]} — {r[1][:60]}  (score={r[3]})")

        # Check sentiment_scores table
        srows = conn.execute(text(
            "SELECT COUNT(*) FROM sentiment_scores WHERE coin='BTC'"
        )).fetchone()
        print(f"  📊 sentiment_scores for BTC: {srows[0]} rows")

except Exception as e:
    test("Database operations", False, str(e))

# ══════════════════════════════════════════════════════════════════════════
# TEST 9: BINANCE LIVE PRICE
# ══════════════════════════════════════════════════════════════════════════
section("TEST 9: BINANCE LIVE PRICES")
for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read())
        price = float(d["lastPrice"])
        change = float(d["priceChangePercent"])
        coin = sym.replace("USDT", "")
        test(f"{coin} live price", price > 0, f"${price:,.2f} ({change:+.2f}%)")
    except Exception as e:
        test(f"{sym} live price", False, str(e))

# ══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════
section("SUMMARY")
total = PASS + FAIL
print(f"  ✅ Passed: {PASS}/{total}")
print(f"  ❌ Failed: {FAIL}/{total}")
if FAIL == 0:
    print(f"\n  🎉 ALL TESTS PASSED — Pipeline is fully operational!")
else:
    print(f"\n  ⚠️  {FAIL} test(s) failed — review above")
