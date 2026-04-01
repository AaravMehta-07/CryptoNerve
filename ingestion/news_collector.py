"""
News Collector — multi-source with strict crypto-only filtering.

Sources (in priority order):
  1. NewsAPI          — broad crypto query, high quality
  2. Google News RSS  — no key needed, near-realtime
  3. CryptoCompare    — fallback, crypto-native feed

Crypto filter:
  Every article passes through _is_crypto_relevant():
  - Must mention at least one crypto keyword in title/description
  - Articles with ONLY generic finance headlines are discarded
  - Coin-specific mentions are detected and tagged

LLM routing:
  Articles are NOT all sent to LLM. They are stored in `news_articles`
  with a `coin_mentions` tag. The SentimentEngine.analyze_and_save()
  pulls only UNANALYZED articles in batches of 50, prioritizing the
  most recent, and sends each one to Mistral 7B with a per-coin prompt.
  This means only crypto-relevant, coin-tagged articles ever reach the LLM.
"""

import hashlib
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
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
    logger.warning("newsapi-python not installed — only Google News + CryptoCompare will be used")


# ---------------------------------------------------------------------------
# Comprehensive crypto keyword list for filtering + coin detection
# ---------------------------------------------------------------------------
CRYPTO_FILTER_KEYWORDS = {
    # Coins + tickers
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp", "ripple",
    "dogecoin", "doge", "cardano", "ada", "avalanche", "avax", "polygon", "matic",
    "chainlink", "link", "litecoin", "ltc", "polkadot", "dot", "uniswap", "uni",
    "shiba", "shib", "pepe", "bnb", "binance", "tron", "trx", "ton", "sui",
    "near", "aptos", "arbitrum", "optimism",
    # Ecosystem terminology
    "crypto", "cryptocurrency", "cryptocurrencies", "blockchain", "defi",
    "nft", "web3", "dao", "altcoin", "stablecoin", "usdt", "usdc", "staking",
    "mining", "miner", "hash rate", "wallet", "exchange", "dex", "cex",
    "token", "tokenomics", "airdrop", "whitepaper", "smart contract",
    "proof of work", "proof of stake", "layer 2", "l2", "layer2",
    # Events / market terms
    "halving", "bull run", "bear market", "whale", "liquidation", "long", "short",
    "futures", "perpetual", "spot etf", "crypto etf", "sec crypto", "cftc",
    "coinbase", "binance", "kraken", "bybit", "okx", "bitfinex",
}

# Compile once at module level for speed
_CRYPTO_FILTER_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in CRYPTO_FILTER_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


class NewsCollector:
    def __init__(self):
        self.newsapi = None
        if _NEWSAPI_AVAILABLE and settings.NEWS_API_KEY:
            self.newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY)
            logger.info("NewsAPI client initialized")
        else:
            logger.warning("NewsAPI key not set — using Google News + CryptoCompare only")

        self.engine = get_engine()
        self.coin_patterns = self._build_coin_patterns()

    # -----------------------------------------------------------------------
    # Coin keyword patterns (per-coin detection)
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
        """Return list of coin symbols that the text explicitly mentions."""
        if not text:
            return []
        return [sym for sym, pat in self.coin_patterns.items() if pat.search(text)]

    # -----------------------------------------------------------------------
    # Crypto relevance gate  ← this is the key filtering step
    # -----------------------------------------------------------------------
    def _is_crypto_relevant(self, title: str, description: str = "") -> bool:
        """
        Returns True only if the article is clearly about crypto/blockchain.
        Checks title first (faster), then falls back to description snippet.
        """
        combined = f"{title} {description or ''}"
        return bool(_CRYPTO_FILTER_RE.search(combined))

    # -----------------------------------------------------------------------
    # Source 1 — NewsAPI
    # -----------------------------------------------------------------------
    def fetch_from_newsapi(self) -> list:
        if not self.newsapi:
            return []

        articles = []
        query = (
            "bitcoin OR ethereum OR solana OR XRP OR dogecoin OR "
            "cryptocurrency OR crypto OR blockchain OR DeFi OR NFT OR "
            "Binance OR Coinbase OR crypto ETF OR SEC crypto"
        )
        try:
            response = self.newsapi.get_everything(
                q=query,
                language="en",
                sort_by="publishedAt",
                page_size=100,
            )
            for article in response.get("articles", []):
                title = article.get("title") or ""
                description = article.get("description") or ""

                # Hard crypto filter — drop anything not crypto-relevant
                if not self._is_crypto_relevant(title, description):
                    continue

                combined_text = f"{title} {description} {article.get('content', '')}"
                coin_mentions = self._detect_coins(combined_text)
                article_id = hashlib.md5(article["url"].encode()).hexdigest()

                articles.append({
                    "article_id": article_id,
                    "source_name": article["source"]["name"],
                    "title": title,
                    "description": description,
                    "content": article.get("content", "")[:5000],
                    "url": article["url"],
                    "published_at": datetime.fromisoformat(
                        article["publishedAt"].replace("Z", "+00:00")
                    ),
                    "coin_mentions": coin_mentions,
                })

            logger.info(f"NewsAPI: {len(articles)} crypto-relevant articles fetched")
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")

        return articles

    # -----------------------------------------------------------------------
    # Source 2 — Google News RSS (no API key required)
    # -----------------------------------------------------------------------
    _GOOGLE_NEWS_QUERIES = [
        "crypto+cryptocurrency",
        "bitcoin+ethereum",
        "solana+XRP+dogecoin",
        "DeFi+blockchain",
        "crypto+SEC+regulation",
        "binance+coinbase+exchange",
    ]

    def fetch_from_google_news(self) -> list:
        articles = []
        base_url = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        for query in self._GOOGLE_NEWS_QUERIES:
            try:
                url = base_url.format(query=query)
                resp = requests.get(url, timeout=10, headers={"User-Agent": "crypto-sentinel/1.0"})
                resp.raise_for_status()
                root = ET.fromstring(resp.content)

                for item in root.findall(".//item"):
                    title = item.findtext("title") or ""
                    description = item.findtext("description") or ""
                    link = item.findtext("link") or ""
                    pub_date_str = item.findtext("pubDate") or ""

                    # Crypto gate
                    if not self._is_crypto_relevant(title, description):
                        continue

                    # Parse pubDate: "Wed, 01 Apr 2026 09:45:00 GMT"
                    try:
                        pub_dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z").replace(
                            tzinfo=timezone.utc
                        )
                    except Exception:
                        pub_dt = datetime.now(timezone.utc)

                    combined_text = f"{title} {description}"
                    coin_mentions = self._detect_coins(combined_text)
                    article_id = hashlib.md5(link.encode()).hexdigest()

                    articles.append({
                        "article_id": article_id,
                        "source_name": "Google News",
                        "title": title,
                        "description": description[:500],
                        "content": description[:5000],
                        "url": link,
                        "published_at": pub_dt,
                        "coin_mentions": coin_mentions,
                    })

            except Exception as e:
                logger.warning(f"Google News RSS error (query={query}): {e}")

        # Deduplicate by article_id within this batch
        seen = set()
        unique = []
        for a in articles:
            if a["article_id"] not in seen:
                seen.add(a["article_id"])
                unique.append(a)

        logger.info(f"Google News: {len(unique)} crypto-relevant articles fetched")
        return unique

    # -----------------------------------------------------------------------
    # Source 3 — CryptoCompare (fallback, always crypto-native)
    # -----------------------------------------------------------------------
    def fetch_from_cryptocompare(self) -> list:
        articles = []
        try:
            url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
            response = requests.get(url, timeout=10)
            data = response.json()

            for article in data.get("Data", [])[:50]:
                title = article.get("title", "")
                body = article.get("body", "")
                combined_text = f"{title} {body}"
                coin_mentions = self._detect_coins(combined_text)
                article_id = hashlib.md5(article["url"].encode()).hexdigest()

                articles.append({
                    "article_id": article_id,
                    "source_name": article.get("source", "CryptoCompare"),
                    "title": title,
                    "description": body[:500],
                    "content": body[:5000],
                    "url": article["url"],
                    "published_at": datetime.fromtimestamp(
                        article["published_on"], tz=timezone.utc
                    ),
                    "coin_mentions": coin_mentions,
                })

            logger.info(f"CryptoCompare: {len(articles)} articles fetched")
        except Exception as e:
            logger.error(f"CryptoCompare error: {e}")

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

        logger.info(f"Saved {saved}/{len(articles)} new news articles")
        return saved

    # -----------------------------------------------------------------------
    # Main entry
    # -----------------------------------------------------------------------
    def run(self) -> int:
        logger.info("Starting multi-source news collection cycle…")

        all_articles: list = []

        # 1. NewsAPI (best quality, paid key)
        all_articles.extend(self.fetch_from_newsapi())

        # 2. Google News RSS (free, near-realtime)
        all_articles.extend(self.fetch_from_google_news())

        # 3. CryptoCompare (always-on fallback)
        all_articles.extend(self.fetch_from_cryptocompare())

        # Global deduplication across all sources by article_id
        seen: set = set()
        unique: list = []
        for a in all_articles:
            if a["article_id"] not in seen:
                seen.add(a["article_id"])
                unique.append(a)

        logger.info(
            f"News cycle: {len(unique)} unique crypto-relevant articles "
            f"(from {len(all_articles)} total fetched across 3 sources)"
        )
        self.save_articles(unique)
        return len(unique)
