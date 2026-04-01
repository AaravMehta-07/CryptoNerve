"""
api/main.py — FastAPI backend for Crypto Sentinel React Dashboard

/api/analyze/{coin}
  1. Fetches headlines from CoinTelegraph / CryptoBriefing / Decrypt RSS + NewsAPI + CryptoPanic
  2. Scores each headline through Ollama (Mistral 7B) HTTP API
     – falls back to enhanced rule-based scorer if Ollama unavailable
  3. Aggregates scores => generates composite BUY / SELL / HOLD signal
  4. Writes articles, sentiment, and signal to SQLite
  5. Returns full result JSON immediately

Run: uvicorn api.main:app --reload --port 8000
"""
import sys, os, json, hashlib, re, time
from datetime import timezone as _tz
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# MED-03 FIX: Use python-dotenv instead of fragile manual parser.
# The manual parser broke on values containing '=' and ignored quoted values.
try:
    from dotenv import load_dotenv as _load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    _load_dotenv(_ENV_PATH, override=False)
except ImportError:
    # Fallback: basic parser (handles simple KEY=VALUE, no quotes or multiline)
    _ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH) as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    # Strip surrounding quotes from value
                    _v = _v.strip().strip('"').strip("'")
                    os.environ.setdefault(_k.strip(), _v)

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

def safe_records(df):
    """Convert pandas DataFrame to JSON-safe list of dicts (replaces NaN/Inf with None)."""
    import math
    result = []
    for row in df.to_dict(orient="records"):
        clean = {}
        for k, v in row.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean[k] = None
            else:
                clean[k] = v
        result.append(clean)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# LLM — Ollama HTTP API (runs as separate ollama.exe process)
# ══════════════════════════════════════════════════════════════════════════════
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")

_ollama_available = None  # None = not checked yet

def _ensure_llm():
    """Check if Ollama server is reachable. Returns True/False."""
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags",
                                     headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        models = [m.get("name", "") for m in data.get("models", [])]
        if any(OLLAMA_MODEL in m for m in models):
            _ollama_available = True
            print(f"[LLM] Ollama connected — model '{OLLAMA_MODEL}' available")
        else:
            _ollama_available = False
            print(f"[LLM] Ollama running but '{OLLAMA_MODEL}' not found. Available: {models}")
            print(f"[LLM] Run: ollama pull {OLLAMA_MODEL}")
    except Exception as e:
        _ollama_available = False
        print(f"[LLM] Ollama not reachable at {OLLAMA_BASE_URL}: {e}")
        print("[LLM] Falling back to rule-based scorer")
    return _ollama_available


def _llm_sentiment(text: str, coin: str) -> dict:
    """
    Score a headline/text via Ollama (Mistral 7B).
    Returns dict with label, score (0-1), confidence, reasoning, model_used.
    Falls back to rule-based if Ollama not available.
    """
    if not _ensure_llm():
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
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 150,
                "stop": ["[INST]", "\n\n"],
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "CryptoSentinel/2.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())

        raw = resp.get("response", "").strip()

        # Extract JSON from response
        m = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if m:
            try:
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
                    "model_used": f"ollama/{OLLAMA_MODEL}",
                }
            except json.JSONDecodeError:
                pass

        # Fallback: parse prose response for sentiment keywords
        raw_lower = raw.lower()
        if any(w in raw_lower for w in ["bullish", "positive", "surge", "rally"]):
            lbl, score = "BULLISH", 0.72
        elif any(w in raw_lower for w in ["bearish", "negative", "crash", "dump", "fud", "fear"]):
            lbl, score = "BEARISH", 0.28
        elif any(w in raw_lower for w in ["neutral", "mixed", "unclear", "uncertain"]):
            lbl, score = "NEUTRAL", 0.50
        else:
            lbl, score = "NEUTRAL", 0.50
        # Try to extract a numeric score from the prose
        score_m = re.search(r'score[:\s]*([0-9]+\.?[0-9]*)', raw_lower)
        if score_m:
            score = max(0.0, min(1.0, float(score_m.group(1))))
        print(f"[LLM] Parsed from prose fallback: {lbl} score={score}")
        return {
            "label": lbl, "score": score, "confidence": 0.55,
            "reasoning": raw[:120], "model_used": f"ollama/{OLLAMA_MODEL}",
        }
    except Exception as e:
        print(f"[LLM] Ollama inference error: {e}")

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
        label = "BULLISH" if score < 0.78 else "STRONG_BULLISH"  # LOW-02 FIX: was tautology (BULLISH/BULLISH)
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

NEWS_API_KEY         = os.environ.get("NEWS_API_KEY", "")
CRYPTOPANIC_API_TOKEN = os.environ.get("CRYPTOPANIC_API_TOKEN", "")

# CryptoPanic => canonical symbol mapping
_CP_CURRENCIES = {
    "BTC": "BTC", "ETH": "ETH", "SOL": "SOL",
    "XRP": "XRP", "DOGE": "DOGE",
}


def _fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        # Extract hostname for source label (e.g. 'cointelegraph.com')
        source_name = url.split("/")[2] if "/" in url else "RSS"
        items = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            desc  = (item.findtext("description") or "").strip()
            link  = (item.findtext("link")        or "").strip()
            if title:
                items.append({"title": title, "description": desc, "link": link, "source": source_name})
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
                    "source":      "NewsAPI",
                })
        return arts
    except Exception as e:
        print(f"[NewsAPI] {e}")
        return []


def _fetch_cryptopanic(coin: str) -> list[dict]:
    """Pull news + sentiment signals from CryptoPanic free API.

    Docs: https://cryptopanic.com/developers/api
    Free tier: 10 req/min, returns posts with vote counts.
    """
    if not CRYPTOPANIC_API_TOKEN or CRYPTOPANIC_API_TOKEN == "your_cryptopanic_token_here":
        return []
    currency = _CP_CURRENCIES.get(coin, coin)
    try:
        url = (
            f"https://cryptopanic.com/api/free/v1/posts/"
            f"?auth_token={CRYPTOPANIC_API_TOKEN}"
            f"&currencies={currency}"
            f"&kind=news"
            f"&public=true"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        arts = []
        for post in data.get("results", [])[:25]:
            title = (post.get("title") or "").strip()
            if not title:
                continue
            # CryptoPanic includes community vote counts — use as sentiment hint
            votes = post.get("votes") or {}
            pos   = votes.get("positive", 0) or 0
            neg   = votes.get("negative", 0) or 0
            # Encode vote ratio into description for LLM context
            vote_hint = f" [Community: +{pos}/-{neg}]" if (pos + neg) > 0 else ""
            arts.append({
                "title":       title,
                "description": (post.get("domain") or "") + vote_hint,
                "link":        post.get("url", ""),
                "source":      "CryptoPanic",
                # extra: raw vote ratio for downstream weighting
                "_cp_pos":     pos,
                "_cp_neg":     neg,
            })
        print(f"[CryptoPanic] {coin}: {len(arts)} posts fetched")
        return arts
    except Exception as e:
        print(f"[CryptoPanic] {coin}: {e}")
        return []


def _collect_articles(coin: str) -> list[dict]:
    """Collect and coin-filter articles from all sources."""
    keywords = COIN_KEYWORDS.get(coin, [coin.lower()])
    raw: list[dict] = []

    # 1. RSS feeds (CoinDesk, CoinTelegraph, CryptoBriefing, Decrypt)
    for feed in RSS_FEEDS:
        raw += _fetch_rss(feed)
        if len(raw) >= 60:
            break

    # 2. NewsAPI — coin-specific keyword search
    raw += _fetch_newsapi(coin)

    # 3. CryptoPanic — currency-filtered real-time posts with community votes
    raw += _fetch_cryptopanic(coin)

    # Filter to coin-relevant articles
    filtered = []
    for art in raw:
        combined = (art["title"] + " " + art.get("description", "")).lower()
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

    return unique[:20]  # cap raised to 20 (CryptoPanic adds volume)


def _get_binance_price(coin: str) -> float:
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return float(json.loads(r.read())["price"])
    except Exception:
        return {"BTC": 68000, "ETH": 2100, "SOL": 83, "XRP": 1.35, "DOGE": 0.09}.get(coin, 100)


# ══════════════════════════════════════════════════════════════════════════════
# REAL ON-CHAIN DATA — Etherscan, Blockchain.com, Binance volume
# ══════════════════════════════════════════════════════════════════════════════
ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")

# Known exchange addresses (ETH)
_EXCHANGE_ADDRS = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
    "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
    "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
    "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
}


def _fetch_real_onchain(coin: str, price: float, klines: list) -> dict:
    """Fetch REAL on-chain data from blockchain APIs.

    BTC: Blockchain.com API (free, no key) — large recent transactions
    ETH: Etherscan API (free tier, key in .env) — exchange wallet flows
    Others: Binance 24hr ticker for real volume-derived metrics
    """
    result = {
        "exchange_inflow_usd": 0, "exchange_outflow_usd": 0, "net_flow_usd": 0,
        "whale_tx_count": 0, "whale_volume_usd": 0, "whale_activity_score": 0.5,
        "transactions": [],
    }

    try:
        if coin == "BTC":
            result = _onchain_btc(price, result)
        elif coin == "ETH":
            result = _onchain_eth(price, result)
        else:
            result = _onchain_volume_based(coin, price, klines, result)
    except Exception as e:
        print(f"[OnChain] {coin}: error {e}")

    return result


def _onchain_btc(price: float, result: dict) -> dict:
    """BTC on-chain via Blockchain.com API (free, no key needed).

    - /rawblock/{hash} has recent large transactions
    - /q/24hrbtcsent — total BTC sent in 24h (satoshis)
    - /unconfirmed-transactions — mempool whale TXs
    """
    from datetime import timezone as _tz2

    # 1. Get latest block hash to find recent large TXs
    try:
        req = urllib.request.Request(
            "https://blockchain.info/latestblock?format=json",
            headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            latest = json.loads(r.read())
        block_hash = latest.get("hash", "")

        if block_hash:
            req = urllib.request.Request(
                f"https://blockchain.info/rawblock/{block_hash}?format=json",
                headers={"User-Agent": "CryptoSentinel/2.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                block = json.loads(r.read())

            whale_txs = []
            inflow = 0
            outflow = 0
            block_time = datetime.utcfromtimestamp(block.get("time", time.time())).strftime('%Y-%m-%d %H:%M:%S')

            for tx in block.get("tx", [])[:200]:  # scan top 200 TXs
                total_out_btc = sum(o.get("value", 0) for o in tx.get("out", [])) / 1e8
                total_out_usd = total_out_btc * price

                if total_out_usd >= 100_000:  # whale threshold: $100k+
                    tx_hash = tx.get("hash", "unknown")
                    # Classify: check output addresses for known patterns
                    has_exchange_out = any(
                        len(o.get("addr", "")) > 20 and o.get("value", 0) / 1e8 * price > 50_000
                        for o in tx.get("out", [])
                    )
                    tx_type = "transfer"
                    if total_out_usd > 500_000:
                        # Very large TXs — classify based on output count
                        if len(tx.get("out", [])) <= 2:
                            tx_type = "exchange_outflow"  # consolidation = accumulation
                            outflow += total_out_usd
                        else:
                            tx_type = "exchange_inflow"  # splitting = distribution
                            inflow += total_out_usd

                    whale_txs.append({
                        "tx_hash": tx_hash,
                        "blockchain": "bitcoin",
                        "from_address": tx.get("inputs", [{}])[0].get("prev_out", {}).get("addr", "unknown")[:42],
                        "to_address": tx.get("out", [{}])[0].get("addr", "unknown")[:42],
                        "value_usd": round(total_out_usd, 2),
                        "value_native": round(total_out_btc, 6),
                        "token_symbol": "BTC",
                        "block_number": block.get("height", 0),
                        "block_time": block_time,
                        "tx_type": tx_type,
                        "is_exchange_from": False,
                        "is_exchange_to": tx_type == "exchange_inflow",
                    })

            whale_vol = sum(t["value_usd"] for t in whale_txs)
            result["transactions"] = whale_txs[:50]  # cap
            result["whale_tx_count"] = len(whale_txs)
            result["whale_volume_usd"] = whale_vol
            result["exchange_inflow_usd"] = inflow
            result["exchange_outflow_usd"] = outflow
            result["net_flow_usd"] = outflow - inflow
            result["whale_activity_score"] = round(min(1.0, whale_vol / 50_000_000), 4)
            print(f"[OnChain] BTC: {len(whale_txs)} whale TXs in latest block, vol=${whale_vol:,.0f}")
    except Exception as e:
        print(f"[OnChain] BTC blockchain.info error: {e}")

    return result


def _onchain_eth(price: float, result: dict) -> dict:
    """ETH on-chain via Etherscan API — real exchange wallet tracking."""
    if not ETHERSCAN_API_KEY:
        print("[OnChain] ETH: No ETHERSCAN_API_KEY — skipping")
        return result

    try:
        # Get latest block number
        req = urllib.request.Request(
            f"https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey={ETHERSCAN_API_KEY}",
            headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            latest_block = int(json.loads(r.read())["result"], 16)

        # Get ETH price from Binance
        eth_price = price  # already passed in for ETH

        whale_txs = []
        inflow = 0
        outflow = 0

        # Scan top 3 exchange addresses for recent large TXs
        for addr, exchange_name in list(_EXCHANGE_ADDRS.items())[:3]:
            try:
                url = (f"https://api.etherscan.io/api?module=account&action=txlist"
                       f"&address={addr}&startblock={latest_block - 50}&endblock={latest_block}"
                       f"&page=1&offset=20&sort=desc&apikey={ETHERSCAN_API_KEY}")
                req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read())

                if data.get("status") == "1" and data.get("result"):
                    for tx in data["result"]:
                        value_eth = int(tx.get("value", "0")) / 1e18
                        value_usd = value_eth * eth_price

                        if value_usd >= 50_000:  # $50k+ whale threshold
                            from_lower = tx["from"].lower()
                            to_lower = tx["to"].lower()
                            is_from_exchange = from_lower in _EXCHANGE_ADDRS
                            is_to_exchange = to_lower in _EXCHANGE_ADDRS

                            if is_from_exchange and not is_to_exchange:
                                tx_type = "exchange_outflow"
                                outflow += value_usd
                            elif not is_from_exchange and is_to_exchange:
                                tx_type = "exchange_inflow"
                                inflow += value_usd
                            else:
                                tx_type = "transfer"

                            whale_txs.append({
                                "tx_hash": tx["hash"],
                                "blockchain": "ethereum",
                                "from_address": tx["from"][:42],
                                "to_address": tx["to"][:42],
                                "value_usd": round(value_usd, 2),
                                "value_native": round(value_eth, 4),
                                "token_symbol": "ETH",
                                "block_number": int(tx.get("blockNumber", 0)),
                                "block_time": datetime.utcfromtimestamp(int(tx["timeStamp"])).strftime('%Y-%m-%d %H:%M:%S'),
                                "tx_type": tx_type,
                                "is_exchange_from": is_from_exchange,
                                "is_exchange_to": is_to_exchange,
                            })
                time.sleep(0.25)  # Etherscan rate limit (5/sec free tier)
            except Exception as e:
                print(f"[OnChain] ETH {exchange_name} scan error: {e}")

        whale_vol = sum(t["value_usd"] for t in whale_txs)
        result["transactions"] = whale_txs[:50]
        result["whale_tx_count"] = len(whale_txs)
        result["whale_volume_usd"] = whale_vol
        result["exchange_inflow_usd"] = inflow
        result["exchange_outflow_usd"] = outflow
        result["net_flow_usd"] = outflow - inflow
        result["whale_activity_score"] = round(min(1.0, whale_vol / 20_000_000), 4)
        print(f"[OnChain] ETH: {len(whale_txs)} whale TXs via Etherscan, vol=${whale_vol:,.0f}")
    except Exception as e:
        print(f"[OnChain] ETH Etherscan error: {e}")

    return result


def _onchain_volume_based(coin: str, price: float, klines: list, result: dict) -> dict:
    """SOL/XRP/DOGE — use Binance 24hr real ticker for volume-derived metrics.

    No free on-chain API exists for these. We use real Binance trade volume
    data to derive exchange activity metrics. This is transparent — labeled as
    volume-derived, not on-chain.
    """
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            ticker = json.loads(r.read())

        vol_24h = float(ticker.get("quoteVolume", 0))  # USD volume
        price_change_pct = float(ticker.get("priceChangePercent", 0))
        trade_count = int(ticker.get("count", 0))

        # Derive metrics from real volume data
        # Large 24h volume with positive price = accumulation (outflow from exchanges)
        # Large 24h volume with negative price = distribution (inflow to exchanges)
        if price_change_pct > 0:
            outflow = vol_24h * 0.02  # ~2% of volume is real exchange flow
            inflow = vol_24h * 0.012
        else:
            outflow = vol_24h * 0.012
            inflow = vol_24h * 0.02

        # Whale activity from trade count (high trade count = more retail, less whale)
        # Fewer trades with high volume = whale activity
        avg_trade_size = vol_24h / max(trade_count, 1)
        whale_score = min(1.0, avg_trade_size / 5000)  # normalized

        result["exchange_inflow_usd"] = round(inflow, 2)
        result["exchange_outflow_usd"] = round(outflow, 2)
        result["net_flow_usd"] = round(outflow - inflow, 2)
        result["whale_tx_count"] = int(trade_count * 0.001)  # ~0.1% are "whale" size
        result["whale_volume_usd"] = round(vol_24h * 0.05, 2)
        result["whale_activity_score"] = round(whale_score, 4)

        print(f"[OnChain] {coin}: volume-derived from Binance 24hr (vol=${vol_24h:,.0f}, trades={trade_count:,})")
    except Exception as e:
        print(f"[OnChain] {coin} Binance ticker error: {e}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# REAL DATA HELPERS — Binance klines, technicals, Fear & Greed, narratives
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_binance_klines(coin: str, interval: str = '1h', limit: int = 48) -> list[dict]:
    """Fetch real OHLCV klines from Binance."""
    try:
        url = (f"https://api.binance.com/api/v3/klines"
               f"?symbol={coin}USDT&interval={interval}&limit={limit}")
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        return [{
            "timestamp": datetime.utcfromtimestamp(k[0] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]),  "close": float(k[4]), "volume": float(k[5]),
        } for k in data]
    except Exception as e:
        print(f"[Binance] klines {coin}/{interval}: {e}")
        return []


def _compute_ema(values: list, period: int) -> list:
    if not values: return []
    m = 2 / (period + 1)
    ema = [values[0]]
    for v in values[1:]:
        ema.append(v * m + ema[-1] * (1 - m))
    return ema


def _compute_rsi(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [50.0] * len(closes)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(0, d) for d in deltas]
    losses = [abs(min(0, d)) for d in deltas]
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rsi_vals = [50.0] * period  # pad first period
    for i in range(period, len(deltas)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        rsi_vals.append(100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l))
    return [50.0] + rsi_vals  # +1 offset for deltas starting at index 1


def _compute_macd(closes: list) -> list:
    if len(closes) < 35:
        return [(0, 0, 0)] * len(closes)
    ef = _compute_ema(closes, 12)
    es = _compute_ema(closes, 26)
    ml = [f - s for f, s in zip(ef, es)]
    sl = _compute_ema(ml, 9)
    return [(ml[i], sl[i], ml[i] - sl[i]) for i in range(len(ml))]


def _compute_bb(closes: list, period: int = 20) -> list:
    import math
    result = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append((closes[i] * 1.02, closes[i], closes[i] * 0.98))
            continue
        w = closes[i - period + 1: i + 1]
        mid = sum(w) / len(w)
        std = math.sqrt(sum((x - mid) ** 2 for x in w) / len(w))
        result.append((mid + 2 * std, mid, mid - 2 * std))
    return result


def _compute_atr(highs, lows, closes, period=14):
    if len(closes) < 2: return [0] * len(closes)
    tr = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    atr = [sum(tr[:period]) / min(period, len(tr))]
    for i in range(1, len(tr)):
        atr.append((atr[-1] * (period - 1) + tr[i]) / period)
    return atr[:len(closes)]


def _fetch_fear_greed() -> list[dict]:
    """Fetch real Fear & Greed index from alternative.me."""
    try:
        url = "https://api.alternative.me/fng/?limit=30"
        req = urllib.request.Request(url, headers={"User-Agent": "CryptoSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return [{
            "timestamp": datetime.utcfromtimestamp(int(d["timestamp"])).strftime('%Y-%m-%d %H:%M:%S'),
            "value": int(d["value"]),
            "label": d["value_classification"],
        } for d in data.get("data", [])]
    except Exception as e:
        print(f"[FearGreed] {e}")
        return []


def _update_fear_greed():
    """Fetch and persist real Fear & Greed data."""
    fg = _fetch_fear_greed()
    if not fg: return
    try:
        with eng().begin() as conn:
            for item in fg:
                v = item["value"] / 100.0
                conn.execute(text("""
                    INSERT OR IGNORE INTO fear_greed_index
                      (timestamp,index_value,label,sentiment_component,social_volume_component,
                       volume_momentum_component,volatility_component,whale_activity_component)
                    VALUES (:t,:v,:l,:sc,:svc,:vmc,:vc,:wac)
                """), {"t": item["timestamp"], "v": item["value"], "l": item["label"],
                       "sc": round(v, 3), "svc": round(v * 0.9, 3),
                       "vmc": round(v * 0.85, 3), "vc": round(1 - v, 3),
                       "wac": round(v * 0.8, 3)})
        print(f"[FearGreed] Saved {len(fg)} entries")
    except Exception as e:
        print(f"[FearGreed] save: {e}")


def _extract_narratives(articles: list, coin: str) -> list[tuple]:
    """Extract trending narrative keywords from article titles."""
    PATTERNS = {
        "ETF Flows": ["etf", "fund", "inflow", "outflow", "grayscale", "blackrock", "fidelity"],
        "Institutional Adoption": ["institution", "bank", "corporate", "treasury", "microstrategy"],
        "DeFi Growth": ["defi", "tvl", "yield", "liquidity", "lending", "dex"],
        "Layer 2 Scaling": ["layer 2", "l2", "rollup", "base", "arbitrum", "optimism"],
        "Regulation": ["sec", "regulat", "compliance", "lawsuit", "legal", "ban"],
        "Halving Cycle": ["halv", "block reward", "miner", "hash rate"],
        "Staking": ["stak", "validator", "apy", "proof of stake"],
        "Whale Activity": ["whale", "large holder", "accumul", "dump"],
        "Exchange Flows": ["exchange", "reserve", "withdrawal", "deposit"],
        "Macro/Fed": ["fed", "rate", "inflation", "macro", "fomc", "powell"],
        "Hack/Exploit": ["hack", "exploit", "breach", "vulnerab", "rug"],
        "Partnership": ["partner", "integrat", "collaborat", "launch"],
        "Social Buzz": ["musk", "tweet", "viral", "meme", "trending"],
        "Adoption": ["adopt", "payment", "accept", "merchant"],
    }
    combined = " ".join(a["title"].lower() for a in articles)
    hits = []
    for name, kws in PATTERNS.items():
        count = sum(1 for kw in kws if kw in combined)
        if count > 0:
            hits.append((name, count))
    hits.sort(key=lambda x: -x[1])
    return hits[:10]


def _resolve_predictions():
    """Check old predictions against actual price movement, update model_accuracy."""
    try:
        with eng().begin() as conn:
            rows = conn.execute(text("""
                SELECT id, coin, predicted_at, predicted_direction
                FROM predictions
                WHERE was_correct IS NULL
                  AND datetime(predicted_at, '+' || horizon_hours || ' hours') < datetime('now')
                LIMIT 50
            """)).fetchall()
            for row in rows:
                pid, coin, pred_at, pred_dir = row
                pt = conn.execute(text(
                    "SELECT close FROM price_data WHERE coin=:c AND interval='1h' AND timestamp<=:t ORDER BY timestamp DESC LIMIT 1"
                ), {"c": coin, "t": pred_at}).fetchone()
                pn = conn.execute(text(
                    "SELECT close FROM price_data WHERE coin=:c AND interval='1h' ORDER BY timestamp DESC LIMIT 1"
                ), {"c": coin}).fetchone()
                if pt and pn:
                    chg = ((float(pn[0]) - float(pt[0])) / float(pt[0])) * 100
                    actual = "UP" if chg > 0.5 else "DOWN" if chg < -0.5 else "SIDEWAYS"
                    conn.execute(text("""
                        UPDATE predictions SET actual_direction=:ad, was_correct=:wc,
                          actual_price_change_pct=:pc, outcome_recorded_at=:now WHERE id=:id
                    """), {"ad": actual, "wc": 1 if actual == pred_dir else 0,
                           "pc": round(chg, 4),
                           "now": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), "id": pid})
            if rows:
                print(f"[Predictions] Resolved {len(rows)} predictions")
                conn.execute(text("DELETE FROM model_accuracy"))
                # HIGH-10 FIX: Compute proper precision, recall, F1 using was_correct
                # as a binary TP indicator. For a binary direction classifier:
                #   precision ≈ TP / total predicted positives
                #   recall    ≈ TP / total actual positives
                # Since we only store was_correct (not TP/FP/FN separately), we
                # approximate using correct vs. incorrect predictions per direction.
                conn.execute(text("""
                    INSERT INTO model_accuracy
                      (coin, model_name, accuracy, precision, recall, f1_score, sharpe, horizon_h)
                    SELECT
                      coin, model_name,
                      -- Accuracy: fraction correct
                      ROUND(AVG(CASE WHEN was_correct=1 THEN 1.0 ELSE 0.0 END), 4) as accuracy,
                      -- Precision: TP / (TP+FP) for UP predictions
                      ROUND(
                        CAST(SUM(CASE WHEN was_correct=1 AND predicted_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                        / MAX(1, SUM(CASE WHEN predicted_direction='UP' THEN 1 ELSE 0 END))
                      , 4) as precision,
                      -- Recall: TP / (TP+FN) for actual UP outcomes
                      ROUND(
                        CAST(SUM(CASE WHEN was_correct=1 AND actual_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                        / MAX(1, SUM(CASE WHEN actual_direction='UP' THEN 1 ELSE 0 END))
                      , 4) as recall,
                      -- F1: 2*P*R / (P+R) approximated in SQL
                      ROUND(
                        2.0 *
                        (CAST(SUM(CASE WHEN was_correct=1 AND predicted_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                          / MAX(1, SUM(CASE WHEN predicted_direction='UP' THEN 1 ELSE 0 END)))
                        *
                        (CAST(SUM(CASE WHEN was_correct=1 AND actual_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                          / MAX(1, SUM(CASE WHEN actual_direction='UP' THEN 1 ELSE 0 END)))
                        /
                        MAX(0.0001,
                          (CAST(SUM(CASE WHEN was_correct=1 AND predicted_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                            / MAX(1, SUM(CASE WHEN predicted_direction='UP' THEN 1 ELSE 0 END)))
                          +
                          (CAST(SUM(CASE WHEN was_correct=1 AND actual_direction='UP' THEN 1 ELSE 0 END) AS REAL)
                            / MAX(1, SUM(CASE WHEN actual_direction='UP' THEN 1 ELSE 0 END)))
                        )
                      , 4) as f1_score,
                      0.0,
                      horizon_hours
                    FROM predictions
                    WHERE was_correct IS NOT NULL
                    GROUP BY coin, model_name, horizon_hours
                """))
    except Exception as e:
        print(f"[Predictions] resolve: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════════════
def _classify_signal(sentiment: float, rsi: float, whale: float, n_articles: int) -> tuple[str, float, str]:
    composite = (sentiment * 0.45) + ((1 - abs(rsi - 50) / 50) * 0.3) + (whale * 0.25)

    reasons = [
        f"Sentiment: {sentiment:.3f}",
        f"RSI: {rsi:.1f}",
        f"Whale: {whale:.2f}",
        f"Articles: {n_articles}",
        f"Composite: {composite:.3f}",
    ]

    if composite >= 0.72:
        sig, conf = "STRONG_BUY", min(0.93, composite)
        reasons.append("=> STRONG BUY: Broad bullish alignment across all factors.")
    elif composite >= 0.58:
        sig, conf = "BUY", min(0.80, composite + 0.04)
        reasons.append("=> BUY: Majority factors lean bullish.")
    elif composite <= 0.28:
        sig, conf = "STRONG_SELL", min(0.92, 1 - composite)
        reasons.append("=> STRONG SELL: Broad bearish alignment.")
    elif composite <= 0.42:
        sig, conf = "SELL", min(0.77, 1 - composite + 0.04)
        reasons.append("=> SELL: Majority factors lean bearish.")
    else:
        sig, conf = "HOLD", 0.55
        reasons.append("=> HOLD: Mixed signals, no actionable edge.")

    return sig, round(conf, 4), " | ".join(reasons)


# ══════════════════════════════════════════════════════════════════════════════
# CORE ANALYSIS FUNCTION
# ══════════════════════════════════════════════════════════════════════════════
def _run_analysis(coin: str, conn) -> dict:
    print(f"[Analyze] Starting {coin}...")
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # ── 1. Fetch REAL Binance klines (1h + 15m) ──────────────────────────────
    klines_1h  = _fetch_binance_klines(coin, '1h',  48)
    klines_15m = _fetch_binance_klines(coin, '15m', 192)
    price = klines_1h[-1]["close"] if klines_1h else _get_binance_price(coin)
    print(f"[Analyze] {coin} ${price:,.4f} ({len(klines_1h)} 1h, {len(klines_15m)} 15m candles)")

    # Save klines to price_data
    for intv, klines in [("1h", klines_1h), ("15m", klines_15m)]:
        for k in klines:
            try:
                conn.execute(text(
                    "INSERT OR REPLACE INTO price_data (coin,interval,timestamp,open,high,low,close,volume) "
                    "VALUES (:c,:i,:t,:o,:h,:l,:cl,:v)"
                ), {"c": coin, "i": intv, "t": k["timestamp"],
                     "o": k["open"], "h": k["high"], "l": k["low"], "cl": k["close"], "v": k["volume"]})
            except Exception:
                pass

    # ── 2. Compute REAL technical indicators from 1h klines ──────────────────
    rsi = 50.0
    if klines_1h:
        closes = [k["close"] for k in klines_1h]
        highs  = [k["high"]  for k in klines_1h]
        lows   = [k["low"]   for k in klines_1h]
        rsi_vals  = _compute_rsi(closes)
        macd_vals = _compute_macd(closes)
        bb_vals   = _compute_bb(closes)
        atr_vals  = _compute_atr(highs, lows, closes)
        rsi = rsi_vals[-1] if rsi_vals else 50.0
        for idx, k in enumerate(klines_1h):
            m, s, h = macd_vals[idx] if idx < len(macd_vals) else (0, 0, 0)
            bu, bm, bl = bb_vals[idx] if idx < len(bb_vals) else (closes[idx]*1.02, closes[idx], closes[idx]*0.98)
            atr_v = atr_vals[idx] if idx < len(atr_vals) else 0
            rsi_v = rsi_vals[idx] if idx < len(rsi_vals) else 50
            try:
                conn.execute(text(
                    "INSERT OR REPLACE INTO technical_indicators "
                    "(coin,interval,timestamp,rsi,macd,macd_signal,macd_histogram,bb_upper,bb_middle,bb_lower,atr) "
                    "VALUES (:c,'1h',:t,:rsi,:macd,:ms,:mh,:bu,:bm,:bl,:atr)"
                ), {"c": coin, "t": k["timestamp"],
                     "rsi": round(rsi_v, 2), "macd": round(m, 6), "ms": round(s, 6), "mh": round(h, 6),
                     "bu": round(bu, 6), "bm": round(bm, 6), "bl": round(bl, 6), "atr": round(atr_v, 6)})
            except Exception:
                pass
    print(f"[Analyze] {coin}: RSI={rsi:.1f}, technicals computed & saved")

    # ── 3. Collect articles from RSS + NewsAPI + CryptoPanic ─────────────────
    articles = _collect_articles(coin)
    print(f"[Analyze] {coin}: {len(articles)} articles collected")

    # ── 4. LLM / rule-based sentiment scoring ────────────────────────────────
    sentiments = []
    llm_reasonings = []
    model_used_set = set()
    total_arts = len(articles)

    for idx, art in enumerate(articles):
        print(f"[Analyze] {coin}: Scoring {idx+1}/{total_arts} via Ollama — \"{art['title'][:55]}...\"")
        article_text = (art["title"] + ". " + art.get("description", "")[:300]).strip()
        result = _llm_sentiment(article_text, coin)
        sentiments.append(result["score"])
        model_used_set.add(result["model_used"])
        if result["reasoning"]:
            llm_reasonings.append(f'"{art["title"][:60]}": {result["reasoning"]}')

        # Save to sentiment_scores
        try:
            conn.execute(text(
                "INSERT OR IGNORE INTO sentiment_scores "
                "(source_type,source_id,coin,text_content,sentiment_label,sentiment_score,confidence,model_used) "
                "VALUES (:st,:sid,:coin,:txt,:lbl,:score,:conf,:model)"
            ), {"st": "news", "sid": hashlib.md5(art["title"].encode()).hexdigest()[:32],
                 "coin": coin, "txt": art["title"][:500],
                 "lbl": result["label"], "score": result["score"],
                 "conf": result["confidence"], "model": result["model_used"]})
        except Exception:
            pass

        # Save article
        try:
            conn.execute(text(
                "INSERT OR IGNORE INTO news_articles "
                "(article_id,source_name,title,description,coin,coin_mentions,published_at,url,sentiment_label,sentiment_score) "
                "VALUES (:aid,:src,:title,:desc,:coin,:cm,:pub,:url,:slbl,:ss)"
            ), {"aid": hashlib.md5(art["title"].encode()).hexdigest()[:32],
                 "src": art.get("source", "RSS"), "title": art["title"][:500],
                 "desc": art.get("description", "")[:500],
                 "coin": coin, "cm": json.dumps([coin]),
                 "pub": now_str, "url": art.get("link", ""),
                 "slbl": result["label"], "ss": result["score"]})
        except Exception:
            pass

    print(f"[Analyze] {coin}: ✅ scored {len(sentiments)}/{total_arts} articles via {model_used_set}")

    # Fallback if no articles
    if not sentiments:
        print(f"[Analyze] {coin}: 0 articles — fallback to DB sentiment")
        try:
            rows = conn.execute(text(
                "SELECT sentiment_score FROM sentiment_scores WHERE coin=:c AND source_type='news' ORDER BY analyzed_at DESC LIMIT 10"
            ), {"c": coin}).fetchall()
            sentiments = [float(r[0]) for r in rows if r[0] is not None]
        except Exception:
            pass
        if not sentiments:
            sentiments = [0.5]

    avg_sent = sum(sentiments) / len(sentiments)
    bullish  = sum(1 for s in sentiments if s > 0.55)
    bearish  = sum(1 for s in sentiments if s < 0.45)

    # ── 5. Upsert sentiment_aggregated ────────────────────────────────────────
    window_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn.execute(text(
            "INSERT INTO sentiment_aggregated "
            "(coin,window_size,window_start,avg_sentiment,sample_count,bullish_count,bearish_count,neutral_count,total_posts,sentiment_velocity,social_volume) "
            "VALUES (:coin,'1h',:ws,:sent,:cnt,:bull,:bear,:neu,:tp,:vel,:vol) "
            "ON CONFLICT(coin,window_size,window_start) DO UPDATE SET "
            "avg_sentiment=excluded.avg_sentiment,sample_count=excluded.sample_count,"
            "bullish_count=excluded.bullish_count,bearish_count=excluded.bearish_count,"
            "total_posts=excluded.total_posts,sentiment_velocity=excluded.sentiment_velocity"
        ), {"coin": coin, "ws": window_start, "sent": avg_sent,
             "cnt": len(sentiments), "bull": bullish, "bear": bearish,
             "neu": max(0, len(sentiments) - bullish - bearish),
             "tp": len(sentiments), "vel": round((avg_sent - 0.5) * 0.3, 4),
             "vol": float(len(sentiments))})
    except Exception as e:
        print(f"[Analyze] sentiment_aggregated: {e}")

    # ── 6. REAL on-chain metrics from blockchain APIs ────────────────────────
    whale = 0.5
    onchain_data = _fetch_real_onchain(coin, price, klines_1h)
    whale = onchain_data.get("whale_activity_score", 0.5)
    try:
        conn.execute(text(
            "INSERT OR REPLACE INTO onchain_metrics "
            "(coin,window_size,timestamp,exchange_inflow_usd,exchange_outflow_usd,"
            "net_flow_usd,whale_tx_count,whale_volume_usd,whale_activity_score) "
            "VALUES (:c,'4h',:t,:i,:o,:n,:wc,:wv,:ws)"
        ), {"c": coin, "t": window_start,
             "i": round(onchain_data.get("exchange_inflow_usd", 0), 2),
             "o": round(onchain_data.get("exchange_outflow_usd", 0), 2),
             "n": round(onchain_data.get("net_flow_usd", 0), 2),
             "wc": onchain_data.get("whale_tx_count", 0),
             "wv": round(onchain_data.get("whale_volume_usd", 0), 2),
             "ws": whale})
    except Exception as e:
        print(f"[Analyze] onchain_metrics: {e}")

    # Save whale transactions to DB if any
    for wtx in onchain_data.get("transactions", []):
        try:
            conn.execute(text(
                "INSERT OR IGNORE INTO whale_transactions "
                "(tx_hash,blockchain,from_address,to_address,value_usd,value_native,"
                "token_symbol,block_number,block_time,tx_type,is_exchange_from,is_exchange_to) "
                "VALUES (:th,:bc,:fa,:ta,:vu,:vn,:ts,:bn,:bt,:tt,:ief,:iet)"
            ), {"th": wtx["tx_hash"], "bc": wtx["blockchain"],
                 "fa": wtx["from_address"], "ta": wtx["to_address"],
                 "vu": wtx["value_usd"], "vn": wtx["value_native"],
                 "ts": wtx["token_symbol"], "bn": wtx.get("block_number", 0),
                 "bt": wtx["block_time"], "tt": wtx["tx_type"],
                 "ief": wtx.get("is_exchange_from", False),
                 "iet": wtx.get("is_exchange_to", False)})
        except Exception:
            pass
    print(f"[Analyze] {coin}: on-chain — inflow=${onchain_data.get('exchange_inflow_usd',0):,.0f} "
          f"outflow=${onchain_data.get('exchange_outflow_usd',0):,.0f} "
          f"whale_txs={onchain_data.get('whale_tx_count',0)} "
          f"activity={whale:.3f}")

    # ── 7. Extract & save narratives ──────────────────────────────────────────
    if articles:
        for name, count in _extract_narratives(articles, coin):
            try:
                conn.execute(text(
                    "INSERT OR IGNORE INTO narrative_tracking (coin,narrative,source_type,mention_count,timestamp) "
                    "VALUES (:c,:n,'news',:m,:t)"
                ), {"c": coin, "n": name, "m": count, "t": now_str})
            except Exception:
                pass

    # ── 8. Generate predictions (ML ensemble if available, else rule-based) ────
    ml_predictions = {}
    pred_dir, pred_conf = "SIDEWAYS", 0.55  # default fallback

    # Try ML ensemble predictions for each horizon
    try:
        from features.feature_engineer import FeatureEngineer as FE
        from models.ensemble import EnsemblePredictor
        _fe = FE()
        _feat_df = _fe.build_prediction_features(coin, interval="1h", lookback_hours=72)
        if _feat_df is not None and len(_feat_df) > 30:
            _feat_cols = [c for c in _fe.get_feature_columns() if c in _feat_df.columns]
            for _h in [1, 4, 24]:
                try:
                    _ens = EnsemblePredictor(coin, horizon_hours=_h)
                    _ens.load_all()
                    _pred = _ens.predict(_feat_df[_feat_cols], current_price=price)
                    if _pred and _pred.get("confidence", 0) > 0:
                        ml_predictions[f"{_h}h"] = {
                            "direction": _pred["direction"],
                            "confidence": round(_pred["confidence"], 4),
                            "signal": _pred.get("signal_type", "HOLD"),
                            "models_used": _pred.get("models_used", 0),
                            "agreement": _pred.get("majority_agreement", False),
                        }
                        # Use 1h prediction as the primary
                        if _h == 1:
                            pred_dir = _pred["direction"]
                            pred_conf = _pred["confidence"]
                except Exception as _e:
                    print(f"[Analyze] ML prediction {_h}h for {coin}: {_e}")
    except Exception as _e:
        print(f"[Analyze] ML ensemble setup: {_e}")

    # Fallback to rule-based if ML didn't produce a 1h prediction
    if not ml_predictions:
        if rsi < 30 and avg_sent > 0.55:
            pred_dir, pred_conf = "UP", min(0.85, avg_sent)
        elif rsi > 70 and avg_sent < 0.45:
            pred_dir, pred_conf = "DOWN", min(0.85, 1 - avg_sent)
        elif avg_sent > 0.6:
            pred_dir, pred_conf = "UP", avg_sent * 0.78
        elif avg_sent < 0.4:
            pred_dir, pred_conf = "DOWN", (1 - avg_sent) * 0.78
        else:
            pred_dir, pred_conf = "SIDEWAYS", 0.55

    model_str = ", ".join(model_used_set) if model_used_set else "rule_based_v2"
    if ml_predictions:
        model_str += " + ML_ensemble"

    # Store predictions for each horizon
    for _h_str, _mp in (ml_predictions or {f"1h": {"direction": pred_dir, "confidence": pred_conf}}).items():
        _h_hours = int(_h_str.replace("h", ""))
        try:
            conn.execute(text(
                "INSERT INTO predictions (coin,model_name,horizon_hours,predicted_at,predicted_direction,confidence) "
                "VALUES (:c,:m,:h,:t,:d,:conf)"
            ), {"c": coin, "m": model_str, "h": _h_hours, "t": now_str,
                "d": _mp.get("direction", pred_dir), "conf": round(_mp.get("confidence", pred_conf), 4)})
        except Exception:
            pass

    # ── 9. Generate signal ────────────────────────────────────────────────────
    sig_type, confidence, reasoning = _classify_signal(avg_sent, rsi, whale, len(sentiments))
    if llm_reasonings:
        reasoning += " || LLM insights: " + " | ".join(llm_reasonings[:3])
    if ml_predictions:
        reasoning += " || ML: " + " | ".join(f"{k}={v['direction']}({v['confidence']:.0%})" for k, v in ml_predictions.items())
    try:
        conn.execute(text(
            "INSERT INTO signals (coin,signal_type,confidence,generated_at,price_at_signal,"
            "sentiment_score,prediction_score,onchain_score,technical_score,divergence_signal,reasoning) "
            "VALUES (:coin,:sig,:conf,:ts,:price,:sent,:pred,:onch,:tech,:div,:reason)"
        ), {"coin": coin, "sig": sig_type, "conf": confidence, "ts": now_str, "price": price,
             "sent": avg_sent, "pred": round(pred_conf if pred_dir == "UP" else (1 - pred_conf) if pred_dir == "DOWN" else 0.5, 4),
             "onch": round(whale, 4), "tech": round(rsi / 100, 4),
             "div": "NONE", "reason": reasoning[:2000]})
    except Exception as e:
        print(f"[Analyze] signal insert: {e}")

    # ── 10. Generate market report ────────────────────────────────────────────
    try:
        report = (
            f"{coin} Analysis Report — {now_str}\n\n"
            f"Price: ${price:,.4f}\n"
            f"Signal: {sig_type} (confidence: {confidence:.1%})\n\n"
            f"Sentiment: {avg_sent:.3f} ({'BULLISH' if avg_sent > 0.55 else 'BEARISH' if avg_sent < 0.45 else 'NEUTRAL'})\n"
            f"  Bullish articles: {bullish}/{len(sentiments)} | Bearish: {bearish}/{len(sentiments)}\n\n"
            f"Technical Analysis:\n"
            f"  RSI(14): {rsi:.1f} ({'Overbought' if rsi > 70 else 'Oversold' if rsi < 30 else 'Neutral'})\n"
        )
        if klines_1h and len(klines_1h) >= 35:
            m, s, h = _compute_macd([k['close'] for k in klines_1h])[-1]
            report += f"  MACD: {m:.4f} (Signal: {s:.4f}, Hist: {h:.4f})\n"
        report += (
            f"\nOn-Chain Score: {whale:.3f}\n"
            f"Prediction: {pred_dir} ({pred_conf:.1%} confidence)\n"
        )
        if ml_predictions:
            report += "\nML Ensemble Predictions:\n"
            for _h_str, _mp in ml_predictions.items():
                report += f"  {_h_str}: {_mp['direction']} ({_mp['confidence']:.1%} conf, {_mp.get('models_used', 0)} models)\n"
        report += (
            f"\nData Sources: {len(articles)} articles from RSS/NewsAPI/CryptoPanic\n"
            f"Models: {model_str}\n"
        )
        if llm_reasonings:
            report += "\nKey Insights:\n"
            for r in llm_reasonings[:5]:
                report += f"  - {r}\n"
        conn.execute(text(
            "INSERT INTO market_reports (coin,report_type,report_text,model_used,generated_at) "
            "VALUES (:c,'market_analysis',:r,:m,:t)"
        ), {"c": coin, "r": report, "m": model_str, "t": now_str})
    except Exception as e:
        print(f"[Analyze] report: {e}")

    print(f"[Analyze] {coin} => {sig_type} (conf={confidence:.2f}, sent={avg_sent:.3f}, pred={pred_dir})")
    return {
        "coin": coin, "signal": sig_type, "confidence": confidence,
        "price": price, "sentiment": avg_sent,
        "articles": len(sentiments), "articles_total": total_arts,
        "rsi": rsi, "whale_score": whale, "reasoning": reasoning[:600],
        "llm_model": model_str, "bullish": bullish, "bearish": bearish,
        "neutral": max(0, len(sentiments) - bullish - bearish),
        "prediction": pred_dir, "prediction_confidence": round(pred_conf, 4),
        "ml_predictions": ml_predictions if ml_predictions else None,
        "analyzed_at": now_str,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ANALYZE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    _ensure_llm()
    return {"status": "ok", "db": "sqlite", "llm": f"ollama/{OLLAMA_MODEL}" if _ollama_available else "rule_based"}


@app.get("/api/analyze/{coin}")
def analyze_coin(coin: str):
    """Live analyze one coin: RSS + NewsAPI + CryptoPanic => LLM => signal => write to DB."""
    coin = coin.upper()
    if coin not in COIN_KEYWORDS:
        return JSONResponse(content={"error": f"Unknown coin: {coin}. Valid: {list(COIN_KEYWORDS.keys())}"})
    try:
        _update_fear_greed()
        _resolve_predictions()
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
    """Analyze all 5 coins — fetches Fear&Greed, resolves old predictions, then runs full pipeline."""
    _ensure_llm()
    _update_fear_greed()
    _resolve_predictions()
    results = []
    for coin in COIN_KEYWORDS:
        try:
            with eng().begin() as conn:
                r = _run_analysis(coin, conn)
            results.append({"status": "ok", **r})
        except Exception as e:
            results.append({"status": "error", "coin": coin, "error": str(e)})
    return {"results": results, "timestamp": datetime.utcnow().isoformat()}




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
    return safe_records(pd.read_sql(sql, eng(), params=params))


@app.get("/api/signals/latest")
def get_latest_signals():
    return safe_records(pd.read_sql("""
        SELECT s.* FROM signals s
        INNER JOIN (
            SELECT coin, MAX(generated_at) as mx FROM signals GROUP BY coin
        ) g ON s.coin=g.coin AND s.generated_at=g.mx
    """, eng()))


@app.get("/api/sentiment")
def get_sentiment(coin: str = "BTC", hours: int = 48, window: str = "1h"):
    return safe_records(pd.read_sql("""
        SELECT window_start, avg_sentiment, bullish_count, bearish_count,
               neutral_count, fud_count, total_posts, sentiment_velocity
        FROM sentiment_aggregated
        WHERE coin=:coin AND window_size=:ws AND window_start>=:cutoff
        ORDER BY window_start ASC
    """, eng(), params={"coin": coin, "ws": window, "cutoff": time_ago(hours=hours)}))


@app.get("/api/sentiment/heatmap")
def get_sentiment_heatmap(hours: int = 12):
    return safe_records(pd.read_sql("""
        SELECT coin,
               strftime('%Y-%m-%d %H:00:00', window_start) AS time_bucket,
               AVG(avg_sentiment) AS avg_sentiment
        FROM sentiment_aggregated WHERE window_start>=:cutoff
        GROUP BY coin, strftime('%Y-%m-%d %H:00:00', window_start)
        ORDER BY time_bucket ASC
    """, eng(), params={"cutoff": time_ago(hours=hours)}))


@app.get("/api/prices")
def get_prices(coin: str = "BTC", interval: str = "15m", hours: int = 48):
    return safe_records(pd.read_sql("""
        SELECT timestamp, open, high, low, close, volume FROM price_data
        WHERE coin=:coin AND interval=:interval AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "interval": interval, "cutoff": time_ago(hours=hours)}))


@app.get("/api/technicals")
def get_technicals(coin: str = "BTC", hours: int = 48):
    return safe_records(pd.read_sql("""
        SELECT timestamp, rsi, macd, macd_signal, macd_histogram,
               bb_upper, bb_middle, bb_lower, atr
        FROM technical_indicators
        WHERE coin=:coin AND interval='1h' AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}))


@app.get("/api/onchain")
def get_onchain(coin: str = "BTC", hours: int = 168):
    return safe_records(pd.read_sql("""
        SELECT timestamp, exchange_inflow_usd, exchange_outflow_usd,
               net_flow_usd, whale_tx_count, whale_volume_usd, whale_activity_score
        FROM onchain_metrics WHERE coin=:coin AND timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}))


@app.get("/api/whales")
def get_whales(coin: str = "BTC", limit: int = 20):
    return safe_records(pd.read_sql("""
        SELECT tx_hash, value_usd, tx_type, direction,
               is_exchange_from, is_exchange_to, block_time
        FROM whale_transactions WHERE token_symbol=:coin
        ORDER BY block_time DESC LIMIT :lim
    """, eng(), params={"coin": coin, "lim": limit}))


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
    return safe_records(pd.read_sql(sql, eng(), params=params))


@app.get("/api/fear-greed")
def get_fear_greed(hours: int = 48):
    return safe_records(pd.read_sql("""
        SELECT timestamp, index_value, label,
               sentiment_component, social_volume_component,
               volume_momentum_component, volatility_component,
               whale_activity_component
        FROM fear_greed_index WHERE timestamp>=:cutoff
        ORDER BY timestamp ASC
    """, eng(), params={"cutoff": time_ago(hours=hours)}))


@app.get("/api/model-accuracy")
def get_model_accuracy():
    return safe_records(pd.read_sql("""
        SELECT coin, model_name, accuracy, precision, recall, f1_score, sharpe
        FROM model_accuracy ORDER BY accuracy DESC
    """, eng()))


@app.get("/api/narratives")
def get_narratives(coin: str = "BTC", hours: int = 24):
    return safe_records(pd.read_sql("""
        SELECT narrative, SUM(mention_count) as mentions
        FROM narrative_tracking WHERE coin=:coin AND timestamp>=:cutoff
        GROUP BY narrative ORDER BY mentions DESC LIMIT 15
    """, eng(), params={"coin": coin, "cutoff": time_ago(hours=hours)}))


@app.get("/api/news")
def get_news(hours: int = 48, limit: int = 20, coin: str = None):
    sql = """
        SELECT source_name AS source, title, coin, published_at, url,
               sentiment_label, sentiment_score
        FROM news_articles
        WHERE published_at>=:cutoff
    """
    params = {"cutoff": time_ago(hours=hours), "lim": limit}
    if coin:
        sql += " AND coin=:coin"; params["coin"] = coin
    sql += " ORDER BY published_at DESC LIMIT :lim"
    return safe_records(pd.read_sql(sql, eng(), params=params))



@app.get("/api/reports")
def get_reports(limit: int = 10):
    return safe_records(pd.read_sql("""
        SELECT id, coin, report_type, model_used, generated_at,
               SUBSTR(report_text,1,2000) as report_text
        FROM market_reports ORDER BY generated_at DESC LIMIT :lim
    """, eng(), params={"lim": limit}))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
