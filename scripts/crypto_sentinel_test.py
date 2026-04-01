#!/usr/bin/env python
"""
crypto_sentinel_test.py — Live system test for all data sources, APIs, and LLM.

Run from the project root:
    python scripts/crypto_sentinel_test.py

Tests:
  1.  Binance API         — fetch live BTC price (no key)
  2.  CoinDesk RSS        — parse latest headlines
  3.  CoinTelegraph RSS   — parse latest headlines
  4.  Crypto Briefing RSS — parse latest headlines
  5.  The Block RSS       — parse latest headlines
  6.  Google News RSS     — crypto query (no key)
  7.  NewsAPI             — live article (key required)
  8.  CryptoCompare       — fallback feed (no key)
  9.  Etherscan API       — ETH block number (key required)
  10. LLM batch test      — run 5 real headlines from sources through Mistral 7B
"""

import sys
import os
import json
import time
import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.table import Table

console = Console()
PASS = "[bold green]PASS[/]"
FAIL = "[bold red]FAIL[/]"
WARN = "[bold yellow]WARN[/]"
HEADERS = {"User-Agent": "crypto-sentinel-test/1.0"}


def section(title):
    console.rule(f"[bold cyan]{title}[/]")


def ok(name, detail=""):
    console.print(f"  [bold green]+ PASS[/]  [bold]{name}[/]  {detail}")
    return True


def fail(name, detail=""):
    console.print(f"  [bold red]- FAIL[/]  [bold]{name}[/]  {detail}")
    return False


# ─────────────────────────────────────────────────────────
# 1. Binance
# ─────────────────────────────────────────────────────────
def test_binance():
    section("1 - Binance (public REST, no key)")
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=8)
        r.raise_for_status()
        price = float(r.json()["price"])
        return ok("BTC live price", f"${price:,.2f}")
    except Exception as e:
        return fail("BTC live price", str(e))


# ─────────────────────────────────────────────────────────
# RSS helper
# ─────────────────────────────────────────────────────────
def fetch_rss_headlines(url, limit=5):
    """Returns list of (title, pubDate) tuples."""
    try:
        r = requests.get(url, timeout=12, headers=HEADERS)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        results = []
        for item in items[:limit]:
            title = re.sub(r"<[^>]+>", "", item.findtext("title") or "").strip()
            pub   = item.findtext("pubDate") or ""
            link  = item.findtext("link") or ""
            if title:
                results.append({"title": title, "pub": pub, "url": link})
        return results
    except Exception:
        return []


def test_rss_feed(name, url):
    try:
        r = requests.get(url, timeout=12, headers=HEADERS)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        if not items:
            return fail(name, "0 items in feed")
        title = re.sub(r"<[^>]+>", "", items[0].findtext("title") or "").strip()
        return ok(name, f"{len(items)} items | Latest: '{title[:65]}...'")
    except Exception as e:
        return fail(name, str(e))


# ─────────────────────────────────────────────────────────
# 2-5. Premium Crypto RSS
# ─────────────────────────────────────────────────────────
def test_premium_rss():
    section("2-5 - Premium Crypto RSS Feeds (no key required)")
    feeds = [
        ("CoinDesk",        "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph",   "https://cointelegraph.com/rss"),
        ("Crypto Briefing", "https://cryptobriefing.com/feed/"),
        ("The Block",       "https://www.theblock.co/rss.xml"),
    ]
    results = {}
    for name, url in feeds:
        results[name] = test_rss_feed(name, url)
        time.sleep(0.4)
    return results


# ─────────────────────────────────────────────────────────
# 6. Google News
# ─────────────────────────────────────────────────────────
def test_google_news():
    section("6 - Google News RSS (no key required)")
    url = "https://news.google.com/rss/search?q=bitcoin+crypto&hl=en-US&gl=US&ceid=US:en"
    return test_rss_feed("Google News", url)


# ─────────────────────────────────────────────────────────
# 7. NewsAPI
# ─────────────────────────────────────────────────────────
def test_newsapi():
    section("7 - NewsAPI")
    key = os.getenv("NEWS_API_KEY")
    if not key:
        return fail("NewsAPI", "NEWS_API_KEY not set")
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": "bitcoin", "language": "en", "pageSize": 3, "apiKey": key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "ok":
            return fail("NewsAPI", data.get("message", "unknown error"))
        total = data.get("totalResults", 0)
        title = data["articles"][0]["title"] if data["articles"] else "(none)"
        return ok("NewsAPI", f"{total} results | '{title[:65]}...'")
    except Exception as e:
        return fail("NewsAPI", str(e))


# ─────────────────────────────────────────────────────────
# 8. CryptoCompare
# ─────────────────────────────────────────────────────────
def test_cryptocompare():
    section("8 - CryptoCompare (fallback, no key)")
    # Try v1 (more reliable) then v2
    for url in [
        "https://min-api.cryptocompare.com/data/news/?lang=EN",
        "https://min-api.cryptocompare.com/data/v2/news/?lang=EN",
    ]:
        try:
            r = requests.get(url, timeout=10, headers=HEADERS)
            r.raise_for_status()
            body = r.json()
            # v1 returns list directly; v2 wraps in {Data: [...]}
            articles = body if isinstance(body, list) else body.get("Data", [])
            if articles:
                return ok("CryptoCompare", f"{len(articles)} articles | '{articles[0]['title'][:65]}...'")
        except Exception:
            continue
    return fail("CryptoCompare", "0 articles from both v1 and v2 endpoints")


# ─────────────────────────────────────────────────────────
# 9. Etherscan — correct free-tier endpoint
# ─────────────────────────────────────────────────────────
def test_etherscan():
    section("9 - Etherscan API")
    key = os.getenv("ETHERSCAN_API_KEY")
    if not key:
        return fail("Etherscan", "ETHERSCAN_API_KEY not set")
    try:
        # Etherscan V2 API (v1 deprecated)
        r = requests.get(
            "https://api.etherscan.io/v2/api",
            params={"chainid": "1", "module": "proxy", "action": "eth_blockNumber", "apikey": key},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        result = data.get("result", "")
        if not result or not isinstance(result, str) or not result.startswith("0x"):
            return fail("Etherscan", f"Unexpected response: {str(data)[:120]}")
        block = int(result, 16)
        return ok("Etherscan", f"Latest ETH block: #{block:,}  (V2 API)")
    except Exception as e:
        return fail("Etherscan", str(e))


# ─────────────────────────────────────────────────────────
# 10. LLM Batch — real headlines from multiple sources
# ─────────────────────────────────────────────────────────
def test_llm_batch():
    section("10 - LLM Batch Test: Real Headlines -> Mistral 7B Sentiment")

    # Collect 1 headline from each RSS source
    sources = [
        ("CoinDesk",        "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph",   "https://cointelegraph.com/rss"),
        ("Crypto Briefing", "https://cryptobriefing.com/feed/"),
        ("The Block",       "https://www.theblock.co/rss.xml"),
        ("Google News",     "https://news.google.com/rss/search?q=bitcoin+ethereum&hl=en-US&gl=US&ceid=US:en"),
    ]

    headlines = []
    console.print("  [dim]Collecting headlines from all sources...[/]")
    for source_name, url in sources:
        items = fetch_rss_headlines(url, limit=1)
        if items:
            headlines.append({"source": source_name, "title": items[0]["title"]})
            console.print(f"  [dim]  [{source_name}] {items[0]['title'][:70]}[/]")
        time.sleep(0.3)

    if not headlines:
        return fail("LLM batch", "Could not fetch any headlines")

    console.print(f"\n  [dim]Loading Mistral 7B GGUF (may take 10-60s)...[/]")

    try:
        from llama_cpp import Llama
        from config.settings import settings

        model_path = settings.LLM_MODEL_PATH
        if not os.path.exists(model_path):
            return fail("LLM model", f"GGUF not found: {model_path}")

        t0 = time.time()
        llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_gpu_layers=int(os.getenv("LLM_N_GPU_LAYERS", "0")),
            n_threads=int(os.getenv("LLM_N_THREADS", "8")),
            verbose=False,
        )
        load_s = time.time() - t0
        console.print(f"  [dim]Model loaded in {load_s:.1f}s[/]\n")

        table = Table(show_header=True, header_style="bold magenta", show_lines=True)
        table.add_column("Source", style="bold", width=16)
        table.add_column("Headline", width=45)
        table.add_column("Label", width=9)
        table.add_column("Score", width=6)
        table.add_column("Confidence", width=10)
        table.add_column("Reasoning", width=40)

        all_ok = True
        for h in headlines:
            prompt = (
                f"[INST] You are a crypto market sentiment analyst.\n\n"
                f'Analyze this crypto headline and return sentiment as JSON.\n'
                f'Do NOT default to 0.9 confidence — calibrate based on signal clarity.\n\n'
                f'TEXT: "{h["title"][:700]}"\n\n'
                f"Output ONLY this JSON, no extra text:\n"
                f'{{"label":"BULLISH|BEARISH|NEUTRAL|FUD",'
                f'"score":0.0_to_1.0,'
                f'"confidence":0.0_to_1.0,'
                f'"reasoning":"one sentence"}}\n\n'
                f"score: 0.0=very bearish, 0.5=neutral, 1.0=very bullish\n"
                f"confidence: how clear is the signal (MUST vary per article)\n\n"
                f"Calibration examples:\n"
                f'>> "Bitcoin ETF gets SEC approval, record $4B inflows"\n'
                f'   {{"label":"BULLISH","score":0.94,"confidence":0.91,"reasoning":"ETF approval unlocks institutional capital."}}\n'
                f'>> "Major exchange hacked, $200M stolen, withdrawals halted"\n'
                f'   {{"label":"FUD","score":0.07,"confidence":0.96,"reasoning":"Hack triggers panic and trust collapse."}}\n'
                f'>> "Fed holds rates; crypto sees mixed volume, unclear direction"\n'
                f'   {{"label":"NEUTRAL","score":0.50,"confidence":0.55,"reasoning":"Mixed macro signals give no clear direction."}}\n'
                f'>> "Regulators debate crypto bill, outcome unknown"\n'
                f'   {{"label":"BEARISH","score":0.30,"confidence":0.63,"reasoning":"Regulatory risk depresses prices but outcome uncertain."}}\n'
                f'>> "Bitcoin hashrate hits all-time high as miners expand"\n'
                f'   {{"label":"BULLISH","score":0.65,"confidence":0.72,"reasoning":"Rising hashrate signals miner confidence."}}\n\n'
                f"Now analyze the TEXT above and output JSON only: [/INST]"
            )
            try:
                t1 = time.time()
                out = llm(prompt, max_tokens=150, temperature=0.1,
                          top_p=0.9, stop=["[INST]", "\n\n"], echo=False)
                infer_s = time.time() - t1
                raw = out["choices"][0]["text"].strip()
                m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
                if m:
                    res = json.loads(m.group())
                    label = res.get("label", "?")
                    score = float(res.get("score", 0))
                    conf  = float(res.get("confidence", 0))
                    reason = res.get("reasoning", "")
                    color = "green" if label == "BULLISH" else "red" if label in ("BEARISH", "FUD") else "yellow"
                    table.add_row(
                        h["source"],
                        h["title"][:44],
                        f"[bold {color}]{label}[/]",
                        f"{score:.2f}",
                        f"{conf:.0%}",
                        reason[:38],
                    )
                    console.print(f"  [dim]  {h['source']}: {label} ({conf:.0%} confidence) [{infer_s:.1f}s][/]")
                else:
                    table.add_row(h["source"], h["title"][:44], "ERR", "-", "-", raw[:38])
                    all_ok = False
            except Exception as e:
                table.add_row(h["source"], h["title"][:44], "ERR", "-", "-", str(e)[:38])
                all_ok = False

            time.sleep(1)  # CPU breathing room

        console.print()
        console.print(table)
        return all_ok

    except ImportError:
        return fail("llama-cpp-python", "Not installed. Run: pip install llama-cpp-python")
    except Exception as e:
        return fail("LLM batch", str(e))


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────
def main():
    console.print("\n[bold magenta]=== CRYPTO SENTINEL - LIVE SYSTEM TEST ===[/]\n")
    console.print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = {}
    results["Binance"]          = test_binance()
    rss = test_premium_rss()
    results.update(rss)
    results["Google News"]      = test_google_news()
    results["NewsAPI"]          = test_newsapi()
    results["CryptoCompare"]    = test_cryptocompare()
    results["Etherscan"]        = test_etherscan()
    results["LLM Batch (5 headlines)"] = test_llm_batch()

    section("SUMMARY")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    notes = {
        "Binance": "Public — no key",
        "CoinDesk": "RSS — no key",
        "CoinTelegraph": "RSS — no key",
        "Crypto Briefing": "RSS — no key",
        "The Block": "RSS — no key",
        "Google News": "RSS — no key",
        "NewsAPI": "Requires NEWS_API_KEY",
        "CryptoCompare": "Always-on fallback",
        "Etherscan": "Requires ETHERSCAN_API_KEY",
        "LLM Batch (5 headlines)": "Local Mistral 7B GGUF",
    }
    table.add_column("Notes")
    passed = 0
    for name, r in results.items():
        table.add_row(name, "[green]PASS[/]" if r else "[red]FAIL[/]", notes.get(name, ""))
        if r:
            passed += 1

    console.print(table)
    console.print(f"\n  Result: {passed}/{len(results)} tests passed\n")
    if passed == len(results):
        console.print("  [bold green]All systems go![/]\n")
    else:
        console.print("  [bold yellow]Some components need attention (see above)[/]\n")


if __name__ == "__main__":
    main()
