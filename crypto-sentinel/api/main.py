"""
api/main.py — FastAPI backend for Crypto Sentinel React Dashboard

/api/analyze/{coin}
  1. Fetches headlines from CoinDesk / CoinTelegraph / Decrypt RSS + NewsAPI
  2. Scores each headline through Mistral 7B GGUF (llama-cpp-python)
     – falls back to enhanced rule-based scorer if GGUF unavailable
  3. Aggregates scores → generates composite BUY / SELL / HOLD signal
  4. Writes articles, sentiment, and signal to SQLite
  5. Returns full result JSON immediately

Run: uvicorn api.main:app --reload --port 8000
"""
import sys, os, json, random, hashlib, re, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Load .env manually (avoid requiring python-dotenv in api layer) ───────────
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_ENV_PATH):
    for _line in open(_ENV_PATH):
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd

from database.connection import get_engine
from database.sql_compat import time_ago
from sqlalchemy import text

app = FastAPI(title="Crypto Sentinel API", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Global exception handler: always return JSON, never HTML ──────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()[-1200:]
    print(f"[API Error] {request.url.path}: {exc}\n{tb}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "error": str(exc), "trace": tb},
    )

def eng(): return get_engine()

# ══════════════════════════════════════════════════════════════════════════════
# LLM SINGLETON — Mistral 7B GGUF loaded once, reused across all requests
# ══════════════════════════════════════════════════════════════════════════════
_llm = None          # llama_cpp.Llama instance once loaded
_llm_ready = False   # True after successful load attempt
_llm_available = False  # True only if model actually loaded

_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "mistral-7b-instruct-v0.1.Q3_K_M.gguf"
)
_N_THREADS   = int(os.environ.get("LLM_N_THREADS",   "6"))
_N_CTX       = int(os.environ.get("LLM_N_CTX",       "2048"))
_N_GPU       = int(os.environ.get("LLM_N_GPU_LAYERS", "0"))

def _ensure_llm():
    """Load the GGUF model on first call. Subsequent calls return cached instance."""
    global _llm, _llm_ready, _llm_available
    if _llm_ready:
        return _llm
    _llm_ready = True
    if not os.path.exists(_MODEL_PATH):
        print(f"[LLM] GGUF not found at {_MODEL_PATH} — using rule-based scorer")
        return None
    try:
        from llama_cpp import Llama
        print(f"[LLM] Loading Mistral 7B GGUF… ({_MODEL_PATH})")
        _llm = Llama(
            model_path=_MODEL_PATH,
            n_ctx=_N_CTX,
            n_threads=_N_THREADS,
            n_gpu_layers=_N_GPU,
            verbose=False,
        )
        _llm_available = True
        print("[LLM] ✅ Mistral 7B loaded and ready")
    except Exception as e:
        print(f"[LLM] ❌ Failed to load model: {e} — using rule-based scorer")
        _llm = None
    return _llm


def _llm_sentiment(text: str, coin: str) -> dict:
    """
    Score a headline/text with Mistral 7B GGUF.
    Returns dict with label, score (0-1), confidence, reasoning, model_used.
    Falls back to rule-based if LLM not available.
    """
    llm = _ensure_llm()
    if llm is None:
        return _rule_sentiment(text)

    prompt = (
        f"[INST] You are a crypto market sentiment analyst specialising in {coin}.\n\n"
        f"Analyze the following crypto news headline. Return ONLY a JSON object.\n\n"
        f'TEXT: "{text[:700]}"\n\n'
        f"Output ONLY this JSON, nothing else:\n"
        f'{{"label":"BULLISH|BEARISH|NEUTRAL|FUD",'
        f'"score":0.0_to_1.0,'
        f'"confidence":0.0_to_1.0,'
        f'"reasoning":"one sentence max"}}\n\n'
        f"score: 0.0=very bearish, 0.5=neutral, 1.0=very bullish\n"
        f"confidence: how clear the signal is\n\n"
        f"Examples:\n"
        f'>> "Bitcoin ETF approval, record $4B inflows"\n'
        f'   {{"label":"BULLISH","score":0.93,"confidence":0.91,"reasoning":"ETF unlocks institutional capital."}}\n'
        f'>> "Exchange hacked, $200M drained, withdrawals paused"\n'
        f'   {{"label":"FUD","score":0.07,"confidence":0.95,"reasoning":"Hack triggers panic selling."}}\n'
        f'>> "Fed holds rates, mixed signals in low volume"\n'
        f'   {{"label":"NEUTRAL","score":0.50,"confidence":0.52,"reasoning":"No clear directional signal."}}\n\n'
        f"Now analyze TEXT: [/INST]"
    )

    try:
        out = llm(
            prompt,
            max_tokens=150,
            temperature=0.1,
            top_p=0.9,
            stop=["[INST]", "\n\n"],
            echo=False,
        )
        raw = out["choices"][0]["text"].strip()

        # Extract JSON from response
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            lbl = data.get("label", "NEUTRAL").upper()
            # Normalize label synonyms
            lbl = {"POSITIVE": "BULLISH", "NEGATIVE": "BEARISH",
                   "FEAR": "FUD", "MIXED": "NEUTRAL", "CAUTIOUS": "NEUTRAL",
                   "UNCERTAIN": "NEUTRAL"}.get(lbl, lbl)
            if lbl not in ("BULLISH", "BEARISH", "NEUTRAL", "FUD"):
                lbl = "NEUTRAL"
            return {
                "label":      lbl,
                "score":      float(data.get("score", 0.5)),
                "confidence": float(data.get("confidence", 0.6)),
                "reasoning":  data.get("reasoning", ""),
                "model_used": "mistral-7b-instruct-q3km",
            }
    except Exception as e:
        print(f"[LLM] inference error: {e}")

    return _rule_sentiment(text)


def _rule_sentiment(text: str) -> dict:
    """Enhanced rule-based fallback sentiment scorer."""
    t = text.lower()
    bull = [
        "bull", "rally", "surge", "breakout", "soar", "pump", "moon", "ath",
        "gain", "rise", "bullish", "positive", "growth", "accumulate",
        "strong", "upside", "recover", "rebound", "adoption", "institutional",
        "etf", "approve", "approval", "partnership", "launch", "upgrade",
        "all-time high", "record", "inflow",
    ]
    bear = [
        "bear", "crash", "dump", "drop", "fall", "bearish", "decline",
        "negative", "loss", "fear", "panic", "liquidat", "lawsuit", "ban",
        "hack", "scam", "fraud", "rug", "plummet", "correction", "downturn",
        "regulation", "sec", "fine", "penalty", "outflow", "sell-off",
    ]
    b = sum(1 for w in bull if w in t)
    s = sum(1 for w in bear if w in t)

    if b == 0 and s == 0:
        score, label = 0.5, "NEUTRAL"
    elif b > s:
        ratio = b / max(b + s, 1)
        score = min(0.5 + ratio * 0.48, 0.97)
        label = "BULLISH" if score < 0.78 else "BULLISH"
    else:
        ratio = s / max(b + s, 1)
        score = max(0.5 - ratio * 0.48, 0.03)
        fud_words = ["hack", "scam", "fraud", "crash", "ban"]
        label = "FUD" if any(w in t for w in fud_words) else "BEARISH"

    return {
        "label":      label,
        "score":      round(score, 4),
        "confidence": 0.65,
        "reasoning":  f"Rule-based: {b} bullish / {s} bearish signals",
        "model_used": "rule_based_v2",
    }

# ══════════════════════════════════════════════════════════════════════════════
# RSS / NEWS COLLECTION
# ══════════════════════════════════════════════════════════════════════════════
COIN_KEYWORDS = {
    "BTC":  ["bitcoin", "btc", "satoshi", "halving"],
    "ETH":  ["ethereum", "eth", "ether", "vitalik", "erc20", "defi", "layer2"],
    "SOL":  ["solana", "sol"],
    "XRP":  ["xrp", "ripple"],
    "DOGE": ["dogecoin", "doge", "musk"],
}

COIN_FULLNAME = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
    "XRP": "XRP Ripple", "DOGE": "Dogecoin",
}

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptobriefing.com/feed/",
    "https://decrypt.co/feed",
]

NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")


def _fetch_rss(url: str, timeout: int = 7) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            link  = (item.findtext("link")        or "").strip()
            if title:
                items.append({"title": title, "description": desc, "link": link})
        return items
    except Exception as e:
        print(f"[RSS] {url}: {e}")
        return []


def _fetch_newsapi(coin: str) -> list[dict]:
    """Pull headlines from NewsAPI (free tier, key in .env)."""
    if not NEWS_API_KEY:
        return []
    try:
        query = urllib.parse.quote(COIN_FULLNAME.get(coin, coin))
        url   = (
            f"https://newsapi.org/v2/everything"
            f"?q={query}&language=en&sortBy=publishedAt"
            f"&pageSize=20&apiKey={NEWS_API_KEY}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        arts = []
        for a in data.get("articles", []):
            if a.get("title"):
                arts.append({
                    "title":       a["title"],
                    "description": a.get("description") or "",
                    "link":        a.get("url", ""),
                })
        return arts
    except Exception as e:
        print(f"[NewsAPI] {e}")
        return []


def _collect_articles(coin: str) -> list[dict]:
    """Collect and coin-filter articles from all sources."""
    keywords = COIN_KEYWORDS.get(coin, [coin.lower()])
    raw: list[dict] = []

    # 1. RSS feeds
    for feed in RSS_FEEDS:
        raw += _fetch_rss(feed)
        if len(raw) >= 60:
            break

    # 2. NewsAPI (richer results, coin-specific)
    raw += _fetch_newsapi(coin)

    # Filter to coin-relevant articles
    filtered = []
    for art in raw:
        combined = (art["title"] + " " + art["description"]).lower()
        if any(kw in combined for kw in keywords):
            filtered.append(art)

    # Deduplicate by title prefix
    seen = set()
    unique = []
    for art in filtered:
        key = art["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(art)

    return unique[:15]  # cap at 15 articles per run


def _get_binance_price(coin: str) -> float:
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return float(json.loads(r.read())["price"])
    except Exception:
        return {"BTC": 68000, "ETH": 2100, "SOL": 83, "XRP": 1.35, "DOGE": 0.09}.get(coin, 100)


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════════════
def _classify_signal(sentiment: float, rsi: float, whale: float, n_articles: int) -> tuple[str, float, str]:
    composite = (sentiment * 0.45) + ((1 - abs(rsi - 50) / 50) * 0.3) + (whale * 0.25)

    reasons = [
        f"LLM avg sentiment: {sentiment:.3f} ({'bullish' if sentiment > 0.55 else 'bearish' if sentiment < 0.45 else 'neutral'})",
        f"RSI: {rsi:.1f} ({'OB' if rsi > 70 else 'OS' if rsi < 30 else 'neutral'})",
        f"Whale score: {whale:.2f}",
        f"Articles processed: {n_articles}",
        f"Composite: {composite:.3f}",
    ]

    if composite >= 0.72:
        sig, conf = "STRONG_BUY", min(0.93, composite)
        reasons.append("→ STRONG BUY: Broad bullish alignment across all factors.")
    elif composite >= 0.58:
        sig, conf = "BUY", min(0.80, composite + 0.04)
        reasons.append("→ BUY: Majority factors lean bullish.")
    elif composite <= 0.28:
        sig, conf = "STRONG_SELL", min(0.92, 1 - composite)
        reasons.append("→ STRONG SELL: Broad bearish alignment.")
    elif composite <= 0.42:
        sig, conf = "SELL", min(0.77, 1 - composite + 0.04)
        reasons.append("→ SELL: Majority factors lean bearish.")
    else:
        sig, conf = "HOLD", 0.55
        reasons.append("→ HOLD: Mixed signals, no actionable edge.")

    return sig, round(conf, 4), " | ".join(reasons)


# ══════════════════════════════════════════════════════════════════════════════
# CORE ANALYSIS FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
def _run_analysis(coin: str, conn) -> dict:
    print(f"[Analyze] Starting {coin}…")
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # 1. Live price
    price = _get_binance_price(coin)
    print(f"[Analyze] {coin} price: ${price:.4f}")

    # 2. Collect articles
    articles = _collect_articles(coin)
    print(f"[Analyze] {coin}: {len(articles)} articles collected")

    # 3. LLM sentiment scoring per article
    sentiments    = []
    llm_reasonings = []
    model_used_set = set()

    for art in articles:
        article_text = (art["title"] + ". " + art["description"][:300]).strip()
        result = _llm_sentiment(article_text, coin)
        sentiments.append(result["score"])
        model_used_set.add(result["model_used"])
        if result["reasoning"]:
            llm_reasonings.append(f'"{art["title"][:60]}": {result["reasoning"]}')

        # Save score to sentiment_scores table
        try:
            conn.execute(
                text("""
                    INSERT OR IGNORE INTO sentiment_scores
                      (source_type, source_id, coin, text_content,
                       sentiment_label, sentiment_score, confidence, model_used)
                    VALUES
                      (:st, :sid, :coin, :txt, :lbl, :score, :conf, :model)
                """),
                {
                    "st":    "news",
                    "sid":   hashlib.md5(art["title"].encode()).hexdigest()[:32],
                    "coin":  coin,
                    "txt":   art["title"][:500],
                    "lbl":   result["label"],
                    "score": result["score"],
                    "conf":  result["confidence"],
                    "model": result["model_used"],
                }
            )
        except Exception:
            pass

        # Save article with dedup
        try:
            conn.execute(
                text("""
                    INSERT OR IGNORE INTO news_articles
                      (article_id, source, title, coin, published_at, url,
                       sentiment_label, sentiment_score)
                    VALUES (:aid, :src, :title, :coin, :pub, :url, :slabel, :sscore)
                """),
                {
                    "aid":    hashlib.md5(art["title"].encode()).hexdigest()[:32],
                    "src":    result["model_used"], "title": art["title"][:500],
                    "coin":   coin, "pub": now_str, "url": art.get("link", ""),
                    "slabel": result["label"], "sscore": result["score"],
                }
            )
        except Exception:
            pass

    print(f"[Analyze] {coin}: LLM scored {len(sentiments)} articles via {model_used_set}")

    avg_sent = sum(sentiments) / len(sentiments) if sentiments else 0.5
    bullish  = sum(1 for s in sentiments if s > 0.55)
    bearish  = sum(1 for s in sentiments if s < 0.45)

    # 4. Upsert sentiment_aggregated
    window_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn.execute(
            text("""
                INSERT INTO sentiment_aggregated
                  (coin, window_size, window_start, avg_sentiment,
                   sample_count, bullish_count, bearish_count, neutral_count,
                   total_posts, sentiment_velocity, social_volume)
                VALUES (:coin,'1h',:ws,:sent,:cnt,:bull,:bear,:neu,:tp,:vel,:vol)
                ON CONFLICT(coin, window_size, window_start) DO UPDATE SET
                  avg_sentiment=excluded.avg_sentiment,
                  sample_count=excluded.sample_count,
                  bullish_count=excluded.bullish_count,
                  bearish_count=excluded.bearish_count,
                  total_posts=excluded.total_posts,
                  sentiment_velocity=excluded.sentiment_velocity
            """),
            {
                "coin": coin, "ws": window_start, "sent": avg_sent,
                "cnt": len(sentiments), "bull": bullish, "bear": bearish,
                "neu": max(0, len(sentiments) - bullish - bearish),
                "tp": len(sentiments),
                "vel": round((avg_sent - 0.5) * 0.3, 4),
                "vol": float(len(sentiments)),
            }
        )
    except Exception as e:
        print(f"[Analyze] sentiment_aggregated upsert: {e}")

    # 5. Fetch RSI & whale score from DB
    try:
        rsi_row = conn.execute(
            text(
                "SELECT rsi FROM technical_indicators WHERE coin=:c ORDER BY timestamp DESC LIMIT 1"
            ), {"c": coin}
        ).fetchone()
        rsi = float(rsi_row[0]) if rsi_row and rsi_row[0] else 50.0
    except Exception:
        rsi = 50.0

    try:
        w_row = conn.execute(
            text(
                "SELECT whale_activity_score FROM onchain_metrics WHERE coin=:c ORDER BY timestamp DESC LIMIT 1"
            ), {"c": coin}
        ).fetchone()
        whale = float(w_row[0]) if w_row and w_row[0] else 0.5
    except Exception:
        whale = 0.5

    # 6. Generate signal
    sig_type, confidence, reasoning = _classify_signal(avg_sent, rsi, whale, len(sentiments))

    # Append LLM article reasonings to signal reasoning
    if llm_reasonings:
        reasoning += " || LLM insights: " + " | ".join(llm_reasonings[:3])

    model_str = ", ".join(model_used_set) if model_used_set else "rule_based_v2"

    # 7. Insert signal
    try:
        conn.execute(
            text("""
                INSERT INTO signals
                  (coin, signal_type, confidence, generated_at, price_at_signal,
                   sentiment_score, prediction_score, onchain_score, technical_score,
                   divergence_signal, reasoning)
                VALUES
                  (:coin,:sig,:conf,:ts,:price,:sent,:pred,:onch,:tech,:div,:reason)
            """),
            {
                "coin": coin, "sig": sig_type, "conf": confidence,
                "ts": now_str, "price": price, "sent": avg_sent,
                "pred": round(avg_sent * 0.6 + (rsi / 100.0) * 0.4, 4),
                "onch": round(whale, 4), "tech": round(rsi / 100.0, 4),
                "div": "NONE", "reason": reasoning[:2000],
            }
        )
    except Exception as e:
        print(f"[Analyze] signal insert: {e}")

    # 8. Insert live price candle
    try:
        spread = price * 0.002
        conn.execute(
            text("""
                INSERT OR IGNORE INTO price_data
                  (coin, interval, timestamp, open, high, low, close, volume)
                VALUES (:coin,'15m',:ts,:o,:h,:l,:c,:v)
            """),
            {
                "coin": coin, "ts": now_str,
                "o": round(price * 0.999, 2), "h": round(price + spread, 2),
                "l": round(price - spread, 2), "c": round(price, 2),
                "v": round(random.uniform(100, 5000), 2),
            }
        )
    except Exception:
        pass

    print(f"[Analyze] {coin} → {sig_type} (conf={confidence:.2f}, sent={avg_sent:.3f})")
    return {
        "coin": coin, "signal": sig_type, "confidence": confidence,
        "price": price, "sentiment": avg_sent, "articles": len(sentiments),
        "rsi": rsi, "whale_score": whale, "reasoning": reasoning[:600],
        "llm_model": model_str, "bullish": bullish, "bearish": bearish,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ANALYZE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    llm_loaded = _llm_ready and _llm_available
    return {"status": "ok", "db": "sqlite", "llm": "mistral-7b-gguf" if llm_loaded else "rule_based"}


@app.get("/api/analyze/{coin}")
def analyze_coin(coin: str):
    """Live analyze one coin: RSS + NewsAPI → Mistral 7B → composite signal → write to DB."""
    coin = coin.upper()
    if coin not in COIN_KEYWORDS:
        return JSONResponse(content={"error": f"Unknown coin: {coin}. Valid: {list(COIN_KEYWORDS.keys())}"})
    try:
        with eng().begin() as conn:
            result = _run_analysis(coin, conn)
        return JSONResponse(content={"status": "ok", **result})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()[-1200:]
        print(f"[Analyze] ERROR for {coin}: {e}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "coin": coin, "error": str(e), "trace": tb[-400:]},
        )


@app.get("/api/analyze-all")
def analyze_all():
    """Analyze all 5 coins sequentially — shares a single LLM instance."""
    _ensure_llm()   # warm up model before loop
    results = []
    for coin in COIN_KEYWORDS:
        try:
            with eng().begin() as conn:
                r = _run_analysis(coin, conn)
            results.append({"status": "ok", **r})
        except Exception as e:
            results.append({"status": "error", "coin": coin, "error": str(e)})
    return {"results": results, "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/seed-demo")
def seed_demo():
    """Re-run init_db.py to seed comprehensive demo data."""
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "scripts/init_db.py"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True, text=True, timeout=90,
        )
        return {
            "status":  "ok" if r.returncode == 0 else "error",
            "stdout":  r.stdout[-2000:] if r.stdout else "",
            "stderr":  r.stderr[-800:]  if r.stderr else "",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# STANDARD READ ENDPOINTS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/signals")
def get_signals(coin: str = None, limit: int = 25):
    cutoff = time_ago(hours=168)
    sql = """
        SELECT id, coin, signal_type, confidence, generated_at,
               price_at_signal, sentiment_score, prediction_score,
               onchain_score, technical_score, divergence_signal, reasoning
        FROM signals WHERE generated_at >= :cutoff
    """
    params = {"cutoff": cutoff}
    if coin:
        sql += " AND coin = :coin"; params["coin"] = coin
    sql += " ORDER BY generated_at DESC LIMIT :lim"; params["lim"] = limit
    return pd.read_sql(sql, eng(), params=params).to_dict(orient="records")


@app.get("/api/signals/latest")
def get_latest_signals():
    return pd.read_sql("""
        SELECT s.* FROM signals s
        INNER JOIN (
            SELECT coin, MAX(generated_at) as mx FROM signals GROUP BY coin
        ) g ON s.coin=g.coin AND s.generated_at=g.mx
    """, eng()).to_dict(orient="records")


@app.get("/api/sentiment")
def get_sentiment(coin: str = "BTC", hours: int = 48, window: str = "1h"):
    return pd.read_sql("""
        SELECT window_start, avg_sentiment, bullish_count, bearish_count,
               neutral_count, fud_count, total_posts, sentiment_velocity
        FROM sentiment_aggregated
        WHERE coin=:coin AND window_size=:ws AND window_start>=:cutoff
        ORDER BY window_start ASC
    """, eng(), params={"coin": coin, "ws": window, "cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/sentiment/heatmap")
def get_sentiment_heatmap(hours: int = 12):
    return pd.read_sql("""
        SELECT coin,
               strftime('%Y-%m-%d %H:00:00', window_start) AS time_bucket,
               AVG(avg_sentiment) AS avg_sentiment
        FROM sentiment_aggregated WHERE window_start>=:cutoff
        GROUP BY coin, strftime('%Y-%m-%d %H:00:00', window_start)
        ORDER BY time_bucket ASC
    """, eng(), params={"cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/prices")
def get_prices(coin: str = "BTC", interval: str = "15m", hours: int = 48):
    return pd.read_sql("""
        SELECT timestamp, open, high, low, close, volume FROM price_data
        WHERE coin=:coin AND interval=:interval AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "interval": interval, "cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/technicals")
def get_technicals(coin: str = "BTC", hours: int = 48):
    return pd.read_sql("""
        SELECT timestamp, rsi, macd, macd_signal, macd_histogram,
               bb_upper, bb_middle, bb_lower, atr
        FROM technical_indicators
        WHERE coin=:coin AND interval='1h' AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/onchain")
def get_onchain(coin: str = "BTC", hours: int = 168):
    return pd.read_sql("""
        SELECT timestamp, exchange_inflow_usd, exchange_outflow_usd,
               net_flow_usd, whale_tx_count, whale_volume_usd, whale_activity_score
        FROM onchain_metrics WHERE coin=:coin AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/whales")
def get_whales(coin: str = "BTC", limit: int = 20):
    return pd.read_sql("""
        SELECT tx_hash, value_usd, tx_type, direction,
               is_exchange_from, is_exchange_to, block_time
        FROM whale_transactions WHERE token_symbol=:coin
        ORDER BY block_time DESC LIMIT :lim
    """, eng(), params={"coin": coin, "lim": limit}).to_dict(orient="records")


@app.get("/api/predictions")
def get_predictions(coin: str = None, horizon: int = 4, limit: int = 50):
    sql = """
        SELECT id, coin, model_name, horizon_hours, predicted_at,
               predicted_direction, confidence, actual_direction,
               was_correct, outcome_recorded_at
        FROM predictions WHERE horizon_hours=:horizon
    """
    params = {"horizon": horizon, "lim": limit}
    if coin:
        sql += " AND coin=:coin"; params["coin"] = coin
    sql += " ORDER BY predicted_at DESC LIMIT :lim"
    return pd.read_sql(sql, eng(), params=params).to_dict(orient="records")


@app.get("/api/fear-greed")
def get_fear_greed(hours: int = 48):
    return pd.read_sql("""
        SELECT timestamp, index_value, label,
               sentiment_component, social_volume_component,
               volume_momentum_component, volatility_component,
               whale_activity_component
        FROM fear_greed_index WHERE timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/model-accuracy")
def get_model_accuracy():
    return pd.read_sql("""
        SELECT coin, model_name, accuracy, precision, recall, f1_score, sharpe
        FROM model_accuracy ORDER BY accuracy DESC
    """, eng()).to_dict(orient="records")


@app.get("/api/narratives")
def get_narratives(coin: str = "BTC", hours: int = 24):
    return pd.read_sql("""
        SELECT narrative, SUM(mention_count) as mentions
        FROM narrative_tracking WHERE coin=:coin AND timestamp>=:cutoff
        GROUP BY narrative ORDER BY mentions DESC LIMIT 15
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}).to_dict(orient="records")


@app.get("/api/news")
def get_news(hours: int = 48, limit: int = 20, coin: str = None):
    sql = """
        SELECT source, title, coin, published_at, url,
               sentiment_label, sentiment_score
        FROM news_articles
        WHERE published_at>=:cutoff
    """
    params = {"cutoff": time_ago(hours=hours), "lim": limit}
    if coin:
        sql += " AND coin=:coin"; params["coin"] = coin
    sql += " ORDER BY published_at DESC LIMIT :lim"
    return pd.read_sql(sql, eng(), params=params).to_dict(orient="records")


@app.get("/api/reports")
def get_reports(limit: int = 10):
    return pd.read_sql("""
        SELECT id, coin, report_type, model_used, generated_at,
               SUBSTR(report_text,1,2000) as report_text
        FROM market_reports ORDER BY generated_at DESC LIMIT :lim
    """, eng(), params={"lim": limit}).to_dict(orient="records")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
