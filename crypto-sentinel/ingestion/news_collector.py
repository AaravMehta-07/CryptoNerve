"""
News Collector — multi-source with strict crypto-only filtering.

Sources (pulled every cycle):
  1. CoinDesk RSS          — https://www.coindesk.com/arc/outboundfeeds/rss/
  2. CoinTelegraph RSS     — https://cointelegraph.com/rss
  3. Crypto Briefing RSS   — https://cryptobriefing.com/feed/
  4. The Block RSS         — https://www.theblock.co/rss.xml
  5. NewsAPI               — broad crypto query (requires API key)
  6. CryptoCompare         — always-on fallback (no key)
  7. Google News RSS       — 6 crypto-specific queries (no key)

Crypto filter:
  Every article passes _is_crypto_relevant() — an 80+ keyword regex
  on title + description. Generic articles are dropped before DB insert.

LLM routing:
  Articles are NOT all sent to LLM. SentimentEngine.analyze_and_save()
  pulls batches of 50 UNANALYZED, coin-tagged articles (newest first)
  and sends each as a focused 900-char prompt to Mistral 7B.
"""

import hashlib
import json
import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from loguru import logger
from config.settings import settings
from config.coins import TRACKED_COINS
from database.connection import get_engine
from sqlalchemy import text

try:
    from newsapi import NewsApiClient
    _NEWSAPI_AVAILABLE = True
except ImportError:
    _NEWSAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Crypto keyword filter
# ---------------------------------------------------------------------------
CRYPTO_FILTER_KEYWORDS = {
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "ripple",
    "dogecoin", "doge", "cardano", "ada", "avalanche", "avax", "polygon", "matic",
    "chainlink", "link", "litecoin", "ltc", "polkadot", "dot", "uniswap", "uni",
    "shiba", "shib", "pepe", "bnb", "binance", "tron", "trx", "ton", "sui",
    "near", "aptos", "arbitrum", "optimism",
    "crypto", "cryptocurrency", "cryptocurrencies", "blockchain", "defi",
    "nft", "web3", "dao", "altcoin", "stablecoin", "usdt", "usdc", "staking",
    "mining", "miner", "hash rate", "wallet", "exchange", "dex", "cex",
    "token", "tokenomics", "airdrop", "whitepaper", "smart contract",
    "proof of work", "proof of stake", "layer 2", "l2", "layer2",
    "halving", "bull run", "bear market", "whale", "liquidation",
    "futures", "perpetual", "spot etf", "crypto etf", "sec crypto", "cftc",
    "coinbase", "kraken", "bybit", "okx", "bitfinex", "coindesk", "cointelegraph",
}

_CRYPTO_FILTER_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in CRYPTO_FILTER_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Premium crypto RSS feeds — always crypto-relevant, no key needed
# ---------------------------------------------------------------------------
CRYPTO_RSS_FEEDS = [
    {"name": "CoinDesk",        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "CoinTelegraph",   "url": "https://cointelegraph.com/rss"},
    {"name": "Crypto Briefing", "url": "https://cryptobriefing.com/feed/"},
    {"name": "The Block",       "url": "https://www.theblock.co/rss.xml"},
]

# Google News RSS — broad crypto queries
GOOGLE_NEWS_QUERIES = [
    "bitcoin+ethereum+crypto",
    "solana+XRP+dogecoin",
    "DeFi+blockchain+NFT",
    "crypto+SEC+regulation",
    "binance+coinbase+exchange",
    "crypto+ETF+halving",
]
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

HEADERS = {"User-Agent": "crypto-sentinel/1.0 (+https://github.com)"}


class NewsCollector:
    def __init__(self):
        self.newsapi = None
        if _NEWSAPI_AVAILABLE and settings.NEWS_API_KEY:
            self.newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)
            logger.info("NewsAPI client initialized")
        self.engine = get_engine()
        self.coin_patterns = self._build_coin_patterns()

    # -----------------------------------------------------------------------
    def _build_coin_patterns(self):
        patterns = {}
        for symbol, info in TRACKED_COINS.items():
            keywords = info["news_keywords"] + [symbol, info["name"]]
            patterns[symbol] = re.compile(
                r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b",
                re.IGNORECASE,
            )
        return patterns

    def _detect_coins(self, text: str) -> list:
        if not text:
            return []
        return [sym for sym, pat in self.coin_patterns.items() if pat.search(text)]

    def _is_crypto_relevant(self, title: str, description: str = "") -> bool:
        return bool(_CRYPTO_FILTER_RE.search(f"{title} {description or ''}"))

    # -----------------------------------------------------------------------
    def _parse_rss_date(self, date_str: str) -> datetime:
        """Parse RFC-2822 pubDate strings robustly."""
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            return parsedate_to_datetime(date_str).astimezone(timezone.utc)
        except Exception:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z").replace(
                    tzinfo=timezone.utc
                )
            except Exception:
                return datetime.now(timezone.utc)

    def _fetch_rss(self, feed_name: str, feed_url: str, apply_crypto_filter: bool = False) -> list:
        """Generic RSS fetcher. Set apply_crypto_filter=False for crypto-native feeds."""
        articles = []
        try:
            resp = requests.get(feed_url, timeout=12, headers=HEADERS)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.findall(".//item"):
                title       = item.findtext("title") or ""
                description = item.findtext("description") or ""
                link        = item.findtext("link") or ""
                pub_date    = item.findtext("pubDate") or ""

                # Strip HTML tags from description (common in RSS)
                description = re.sub(r"<[^>]+>", "", description).strip()

                if apply_crypto_filter and not self._is_crypto_relevant(title, description):
                    continue

                combined    = f"{title} {description}"
                coin_mentions = self._detect_coins(combined)
                article_id  = hashlib.md5(link.encode()).hexdigest()

                articles.append({
                    "article_id":   article_id,
                    "source_name":  feed_name,
                    "title":        title,
                    "description":  description[:500],
                    "content":      description[:5000],
                    "url":          link,
                    "published_at": self._parse_rss_date(pub_date),
                    "coin_mentions": json.dumps(coin_mentions),
                })

        except Exception as e:
            logger.warning(f"RSS fetch error [{feed_name}]: {e}")

        return articles

    # -----------------------------------------------------------------------
    # Source 1-4 — Premium crypto RSS feeds (always crypto-native)
    # -----------------------------------------------------------------------
    def fetch_from_crypto_rss(self) -> list:
        articles = []
        for feed in CRYPTO_RSS_FEEDS:
            batch = self._fetch_rss(feed["name"], feed["url"], apply_crypto_filter=False)
            logger.info(f"{feed['name']}: {len(batch)} articles fetched")
            articles.extend(batch)
            time.sleep(0.5)   # polite crawl delay
        return articles

    # -----------------------------------------------------------------------
    # Source 5 — NewsAPI
    # -----------------------------------------------------------------------
    def fetch_from_newsapi(self) -> list:
        if not self.newsapi:
            return []
        articles = []
        query = (
            "bitcoin OR ethereum OR solana OR XRP OR dogecoin OR "
            "cryptocurrency OR crypto OR blockchain OR DeFi OR "
            "Binance OR Coinbase OR crypto ETF OR SEC crypto"
        )
        try:
            response = self.newsapi.get_everything(
                q=query, language="en", sort_by="publishedAt", page_size=100
            )
            for article in response.get("articles", []):
                title       = article.get("title") or ""
                description = article.get("description") or ""
                if not self._is_crypto_relevant(title, description):
                    continue
                combined      = f"{title} {description} {article.get('content', '')}"
                coin_mentions = self._detect_coins(combined)
                article_id    = hashlib.md5(article["url"].encode()).hexdigest()
                articles.append({
                    "article_id":   article_id,
                    "source_name":  article["source"]["name"],
                    "title":        title,
                    "description":  description,
                    "content":      article.get("content", "")[:5000],
                    "url":          article["url"],
                    "published_at": datetime.fromisoformat(
                        article["publishedAt"].replace("Z", "+00:00")
                    ),
                    "coin_mentions": json.dumps(coin_mentions),
                })
            logger.info(f"NewsAPI: {len(articles)} crypto-relevant articles")
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
        return articles

    # -----------------------------------------------------------------------
    # Source 6 — CryptoCompare (always-on fallback, no key)
    # -----------------------------------------------------------------------
    def fetch_from_cryptocompare(self) -> list:
        articles = []
        try:
            resp = requests.get(
                "https://min-api.cryptocompare.com/data/v2/news/?lang=EN", timeout=10
            )
            for article in resp.json().get("Data", [])[:50]:
                title = article.get("title", "")
                body  = article.get("body", "")
                article_id = hashlib.md5(article["url"].encode()).hexdigest()
                articles.append({
                    "article_id":   article_id,
                    "source_name":  article.get("source", "CryptoCompare"),
                    "title":        title,
                    "description":  body[:500],
                    "content":      body[:5000],
                    "url":          article["url"],
                    "published_at": datetime.fromtimestamp(article["published_on"], tz=timezone.utc),
                    "coin_mentions": json.dumps(self._detect_coins(f"{title} {body}")),
                })
            logger.info(f"CryptoCompare: {len(articles)} articles")
        except Exception as e:
            logger.error(f"CryptoCompare error: {e}")
        return articles

    # -----------------------------------------------------------------------
    # Source 7 — Google News RSS
    # -----------------------------------------------------------------------
    def fetch_from_google_news(self) -> list:
        articles = []
        for q in GOOGLE_NEWS_QUERIES:
            url = GOOGLE_NEWS_BASE.format(q=q)
            batch = self._fetch_rss("Google News", url, apply_crypto_filter=True)
            articles.extend(batch)
            time.sleep(0.3)
        logger.info(f"Google News: {len(articles)} crypto-relevant articles")
        return articles

    # -----------------------------------------------------------------------
    # DB save
    # -----------------------------------------------------------------------
    def save_articles(self, articles: list) -> int:
        if not articles:
            return 0
        saved = 0
        insert_sql = text("""
            INSERT INTO news_articles
                (article_id, source_name, title, description, content, url, published_at, coin_mentions)
            VALUES
                (:article_id, :source_name, :title, :description, :content, :url, :published_at, :coin_mentions)
            ON CONFLICT (article_id) DO NOTHING
        """)
        try:
            with self.engine.begin() as conn:
                for article in articles:
                    try:
                        conn.execute(insert_sql, article)
                        saved += 1
                    except Exception as e:
                        logger.debug(f"Article insert skipped ({article.get('article_id')}): {e}")
        except Exception as e:
            logger.error(f"Batch article insert error: {e}")
        logger.info(f"Saved {saved}/{len(articles)} new articles to DB")
        return saved

    # -----------------------------------------------------------------------
    # Main entry
    # -----------------------------------------------------------------------
    def run(self) -> int:
        logger.info("Starting multi-source news collection cycle…")
        all_articles: list = []

        all_articles.extend(self.fetch_from_crypto_rss())    # CoinDesk, CoinTelegraph, Crypto Briefing, The Block
        all_articles.extend(self.fetch_from_newsapi())        # NewsAPI (key required)
        all_articles.extend(self.fetch_from_cryptocompare())  # CryptoCompare (always on)
        all_articles.extend(self.fetch_from_google_news())    # Google News RSS

        # Deduplicate across all sources
        seen: set = set()
        unique: list = []
        for a in all_articles:
            if a["article_id"] not in seen:
                seen.add(a["article_id"])
                unique.append(a)

        logger.info(
            f"News cycle complete: {len(unique)} unique articles "
            f"(from {len(all_articles)} total across all sources)"
        )
        self.save_articles(unique)
        return len(unique)
