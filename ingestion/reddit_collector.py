import praw
import re
from datetime import datetime, timezone
from loguru import logger
from config.settings import settings
from config.coins import TRACKED_COINS
from database.connection import get_engine
from sqlalchemy import text
import pandas as pd


class RedditCollector:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )
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

    def fetch_posts(self, limit_per_subreddit=50):
        all_subreddits = set()
        for coin_info in TRACKED_COINS.values():
            all_subreddits.update(coin_info["subreddits"])

        posts = []
        for subreddit_name in all_subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                for post in subreddit.new(limit=limit_per_subreddit):
                    combined_text = f"{post.title} {post.selftext or ''}"
                    coin_mentions = self._detect_coins(combined_text)

                    if not coin_mentions:
                        for sym, info in TRACKED_COINS.items():
                            if subreddit_name in info["subreddits"] and subreddit_name != "cryptocurrency":
                                coin_mentions = [sym]
                                break

                    posts.append({
                        "post_id": post.id,
                        "subreddit": subreddit_name,
                        "title": post.title,
                        "selftext": post.selftext[:5000] if post.selftext else None,
                        "author": str(post.author) if post.author else "[deleted]",
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "created_utc": datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                        "url": post.url,
                        "coin_mentions": coin_mentions,
                    })

                logger.info(f"Fetched {limit_per_subreddit} posts from r/{subreddit_name}")
            except Exception as e:
                logger.error(f"Error fetching r/{subreddit_name}: {e}")

        return posts

    def fetch_comments(self, post_ids, limit_per_post=10):
        comments = []
        for post_id in post_ids[:20]:
            try:
                submission = self.reddit.submission(id=post_id)
                submission.comments.replace_more(limit=0)
                for comment in submission.comments[:limit_per_post]:
                    coin_mentions = self._detect_coins(comment.body)
                    comments.append({
                        "comment_id": comment.id,
                        "post_id": post_id,
                        "body": comment.body[:3000],
                        "author": str(comment.author) if comment.author else "[deleted]",
                        "score": comment.score,
                        "created_utc": datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                        "coin_mentions": coin_mentions,
                    })
            except Exception as e:
                logger.error(f"Error fetching comments for {post_id}: {e}")
        return comments

    def save_posts(self, posts):
        """Batch insert posts using raw SQL with proper TEXT[] type (CRIT-04, MED-01)."""
        if not posts:
            return 0

        saved = 0
        insert_sql = text("""
            INSERT INTO reddit_posts
                (post_id, subreddit, title, selftext, author, score, num_comments, created_utc, url, coin_mentions)
            VALUES
                (:post_id, :subreddit, :title, :selftext, :author, :score, :num_comments, :created_utc, :url, :coin_mentions)
            ON CONFLICT (post_id) DO NOTHING
        """)
        try:
            with self.engine.begin() as conn:
                for post in posts:
                    try:
                        conn.execute(insert_sql, {
                            **{k: v for k, v in post.items() if k != "coin_mentions"},
                            "coin_mentions": post["coin_mentions"],  # list → psycopg2 passes as TEXT[]
                        })
                        saved += 1
                    except Exception as e:
                        logger.debug(f"Post insert skipped ({post.get('post_id')}): {e}")
        except Exception as e:
            logger.error(f"Batch post insert error: {e}")

        logger.info(f"Saved {saved}/{len(posts)} new Reddit posts")
        return saved

    def save_comments(self, comments):
        """Batch insert comments using raw SQL with proper TEXT[] type (CRIT-04, MED-01)."""
        if not comments:
            return 0

        saved = 0
        insert_sql = text("""
            INSERT INTO reddit_comments
                (comment_id, post_id, body, author, score, created_utc, coin_mentions)
            VALUES
                (:comment_id, :post_id, :body, :author, :score, :created_utc, :coin_mentions)
            ON CONFLICT (comment_id) DO NOTHING
        """)
        try:
            with self.engine.begin() as conn:
                for comment in comments:
                    try:
                        conn.execute(insert_sql, {
                            **{k: v for k, v in comment.items() if k != "coin_mentions"},
                            "coin_mentions": comment["coin_mentions"],
                        })
                        saved += 1
                    except Exception as e:
                        logger.debug(f"Comment insert skipped ({comment.get('comment_id')}): {e}")
        except Exception as e:
            logger.error(f"Batch comment insert error: {e}")

        logger.info(f"Saved {saved}/{len(comments)} new Reddit comments")
        return saved

    def run(self):
        logger.info("Starting Reddit collection cycle...")
        posts = self.fetch_posts(limit_per_subreddit=50)
        self.save_posts(posts)

        high_engagement = [p["post_id"] for p in posts if p["score"] > 5 or p["num_comments"] > 3]
        if high_engagement:
            comments = self.fetch_comments(high_engagement)
            self.save_comments(comments)

        logger.info(f"Reddit cycle complete: {len(posts)} posts processed")
        return len(posts)
