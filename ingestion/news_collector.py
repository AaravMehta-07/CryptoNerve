import hashlib
from datetime import datetime, timezone
from newsapi import NewsApiClient
from loguru import logger
from config.settings import settings
from config.coins import TRACKED_COINS
from database.connection import get_engine
import pandas as pd
import re
import requests


class NewsCollector:
    def __init__(self):
        self.newsapi = NewsApiClient(api_key=settings.NEWS_API_KEY) if settings.NEWS_API_KEY else None
        self.engine = get_engine()
        self.coin_patterns = self._build_coin_patterns()

    def _build_coin_patterns(self):
        patterns = {}
        for symbol, info in TRACKED_COINS.items():
            keywords = info["news_keywords"] + [symbol, info["name"]]
            pattern = re.compile(
                r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b",
                re.IGNORECASE,
            )
            patterns[symbol] = pattern
        return patterns

    def _detect_coins(self, text):
        if not text:
            return []
        mentions = []
        for symbol, pattern in self.coin_patterns.items():
            if pattern.search(text):
                mentions.append(symbol)
        return mentions

    def fetch_from_newsapi(self):
        if not self.newsapi:
            logger.warning("NewsAPI key not configured, using fallback")
            return self.fetch_from_cryptocompare()

        articles = []
        try:
            query = "cryptocurrency OR bitcoin OR ethereum OR solana OR crypto"
            response = self.newsapi.get_everything(
                q=query, language="en", sort_by="publishedAt", page_size=50
            )
            for article in response.get("articles", []):
                combined_text = f"{article['title']} {article.get('description', '')} {article.get('content', '')}"
                coin_mentions = self._detect_coins(combined_text)
                article_id = hashlib.md5(article["url"].encode()).hexdigest()

                articles.append({
                    "article_id": article_id,
                    "source_name": article["source"]["name"],
                    "title": article["title"],
                    "description": article.get("description"),
                    "content": article.get("content", "")[:5000],
                    "url": article["url"],
                    "published_at": datetime.fromisoformat(
                        article["publishedAt"].replace("Z", "+00:00")
                    ),
                    "coin_mentions": coin_mentions,
                })

            logger.info(f"Fetched {len(articles)} articles from NewsAPI")
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            articles = self.fetch_from_cryptocompare()

        return articles

    def fetch_from_cryptocompare(self):
        articles = []
        try:
            url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
            response = requests.get(url, timeout=10)
            data = response.json()

            for article in data.get("Data", [])[:50]:
                combined_text = f"{article['title']} {article.get('body', '')}"
                coin_mentions = self._detect_coins(combined_text)
                article_id = hashlib.md5(article["url"].encode()).hexdigest()

                articles.append({
                    "article_id": article_id,
                    "source_name": article.get("source", "CryptoCompare"),
                    "title": article["title"],
                    "description": article.get("body", "")[:500],
                    "content": article.get("body", "")[:5000],
                    "url": article["url"],
                    "published_at": datetime.fromtimestamp(
                        article["published_on"], tz=timezone.utc
                    ),
                    "coin_mentions": coin_mentions,
                })

            logger.info(f"Fetched {len(articles)} articles from CryptoCompare")
        except Exception as e:
            logger.error(f"CryptoCompare error: {e}")

        return articles

    def save_articles(self, articles):
        if not articles:
            return 0
        saved = 0
        for article in articles:
            try:
                article_copy = article.copy()
                article_copy["coin_mentions"] = "{" + ",".join(article_copy["coin_mentions"]) + "}"
                pd.DataFrame([article_copy]).to_sql(
                    "news_articles", self.engine, if_exists="append", index=False, method="multi"
                )
                saved += 1
            except Exception:
                pass

        logger.info(f"Saved {saved}/{len(articles)} new news articles")
        return saved

    def run(self):
        logger.info("Starting news collection cycle...")
        articles = self.fetch_from_newsapi()
        self.save_articles(articles)
        logger.info(f"News cycle complete: {len(articles)} articles processed")
        return len(articles)
