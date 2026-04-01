import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger
from sentiment.ollama_analyzer import OllamaAnalyzer
from sentiment.finbert_analyzer import FinBERTAnalyzer
from sentiment.narrative_detector import NarrativeDetector
from database.connection import get_engine
from config.coins import TRACKED_COINS


class SentimentEngine:
    def __init__(self):
        self.ollama = OllamaAnalyzer()
        self.finbert = FinBERTAnalyzer()
        self.narrative_detector = NarrativeDetector()
        self.engine = get_engine()

        if self.ollama.available:
            self.primary_analyzer = self.ollama
            logger.info("Using Ollama (Mistral) as primary sentiment analyzer")
        elif self.finbert.available:
            self.primary_analyzer = self.finbert
            logger.info("Using FinBERT as fallback sentiment analyzer")
        else:
            logger.error("NO sentiment analyzer available!")
            self.primary_analyzer = None

    def get_unanalyzed_texts(self, limit=50):
        query = """
        (
            SELECT
                'reddit_post' as source_type,
                post_id as source_id,
                title || ' ' || COALESCE(selftext, '') as text,
                coin_mentions,
                created_utc
            FROM reddit_posts
            WHERE post_id NOT IN (SELECT source_id FROM sentiment_scores WHERE source_type = 'reddit_post')
            ORDER BY created_utc DESC
            LIMIT %s
        )
        UNION ALL
        (
            SELECT
                'reddit_comment' as source_type,
                comment_id as source_id,
                body as text,
                coin_mentions,
                created_utc
            FROM reddit_comments
            WHERE comment_id NOT IN (SELECT source_id FROM sentiment_scores WHERE source_type = 'reddit_comment')
            ORDER BY created_utc DESC
            LIMIT %s
        )
        UNION ALL
        (
            SELECT
                'news' as source_type,
                article_id as source_id,
                title || ' ' || COALESCE(description, '') as text,
                coin_mentions,
                published_at as created_utc
            FROM news_articles
            WHERE article_id NOT IN (SELECT source_id FROM sentiment_scores WHERE source_type = 'news')
            ORDER BY published_at DESC
            LIMIT %s
        )
        """
        try:
            df = pd.read_sql(query, self.engine, params=(limit, limit, limit))
            texts = []
            for _, row in df.iterrows():
                coins = row["coin_mentions"]
                if isinstance(coins, str):
                    coins = coins.strip("{}").split(",") if coins.strip("{}") else []
                elif not isinstance(coins, list):
                    coins = []

                if not coins:
                    coins = ["BTC"]

                for coin in coins:
                    coin = coin.strip()
                    if coin in TRACKED_COINS:
                        texts.append({
                            "source_type": row["source_type"],
                            "source_id": row["source_id"],
                            "text": row["text"][:2000],
                            "coin": coin,
                        })
            return texts
        except Exception as e:
            logger.error(f"Error getting unanalyzed texts: {e}")
            return []

    def analyze_and_save(self, limit=50):
        if not self.primary_analyzer:
            logger.error("No analyzer available")
            return 0

        texts = self.get_unanalyzed_texts(limit)
        if not texts:
            logger.info("No new texts to analyze")
            return 0

        logger.info(f"Analyzing {len(texts)} texts...")
        results = self.primary_analyzer.batch_analyze(texts)

        saved = 0
        for result in results:
            try:
                record = {
                    "source_type": result["source_type"],
                    "source_id": result["source_id"],
                    "coin": result["coin"],
                    "text_content": result["text_content"],
                    "sentiment_label": result["label"],
                    "sentiment_score": result["score"],
                    "confidence": result["confidence"],
                    "model_used": result["model"],
                }
                pd.DataFrame([record]).to_sql(
                    "sentiment_scores", self.engine, if_exists="append", index=False
                )
                saved += 1
            except Exception:
                pass

        logger.info(f"Saved {saved}/{len(results)} sentiment scores")
        return saved

    def aggregate_sentiment(self, coin, window_hours=4):
        query = f"""
        SELECT
            sentiment_label,
            sentiment_score,
            confidence,
            text_content,
            analyzed_at
        FROM sentiment_scores
        WHERE coin = '{coin}'
        AND analyzed_at > NOW() - INTERVAL '{window_hours} hours'
        ORDER BY analyzed_at DESC
        """
        try:
            df = pd.read_sql(query, self.engine)
            if df.empty:
                return None

            avg_sentiment = df["sentiment_score"].mean()
            median_sentiment = df["sentiment_score"].median()
            sentiment_std = df["sentiment_score"].std()

            label_counts = df["sentiment_label"].value_counts()
            bullish_count = int(label_counts.get("BULLISH", 0))
            bearish_count = int(label_counts.get("BEARISH", 0))
            neutral_count = int(label_counts.get("NEUTRAL", 0))
            fud_count = int(label_counts.get("FUD", 0))

            if len(df) >= 6:
                recent = df.head(len(df) // 2)["sentiment_score"].mean()
                older = df.tail(len(df) // 2)["sentiment_score"].mean()
                velocity = recent - older
            else:
                velocity = 0.0

            all_texts = df["text_content"].tolist()
            narratives = self.narrative_detector.detect_narratives(all_texts)

            result = {
                "coin": coin,
                "window_start": datetime.now(timezone.utc) - timedelta(hours=window_hours),
                "window_end": datetime.now(timezone.utc),
                "window_size": f"{window_hours}h",
                "avg_sentiment": round(avg_sentiment, 4),
                "median_sentiment": round(median_sentiment, 4),
                "sentiment_std": round(sentiment_std, 4) if not pd.isna(sentiment_std) else 0.0,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
                "fud_count": fud_count,
                "total_posts": len(df),
                "sentiment_velocity": round(velocity, 4),
                "sentiment_acceleration": 0.0,
                "dominant_narratives": [n[0] for n in narratives[:5]],
                "social_volume": len(df),
            }

            try:
                save_record = result.copy()
                save_record["dominant_narratives"] = (
                    "{" + ",".join(save_record["dominant_narratives"]) + "}"
                )
                pd.DataFrame([save_record]).to_sql(
                    "sentiment_aggregated", self.engine, if_exists="append", index=False
                )
            except Exception:
                pass

            return result
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            return None

    def get_sentiment_history(self, coin, hours=72):
        query = f"""
        SELECT avg_sentiment, window_start
        FROM sentiment_aggregated
        WHERE coin = '{coin}' AND window_size = '1h'
        AND window_start > NOW() - INTERVAL '{hours} hours'
        ORDER BY window_start ASC
        """
        try:
            return pd.read_sql(query, self.engine)
        except Exception:
            return pd.DataFrame()

    def run(self):
        logger.info("Starting sentiment analysis cycle...")
        analyzed = self.analyze_and_save(limit=50)

        for coin in TRACKED_COINS.keys():
            for window in [1, 4, 24]:
                self.aggregate_sentiment(coin, window)

        logger.info(f"Sentiment cycle complete: {analyzed} texts analyzed")
        return analyzed
