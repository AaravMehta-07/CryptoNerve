"""
SQLAlchemy ORM models (optional — raw SQL is used for most operations).
These models are available for future ORM-based extensions.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ARRAY
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class RedditPost(Base):
    __tablename__ = "reddit_posts"
    id = Column(Integer, primary_key=True)
    post_id = Column(String(20), unique=True, nullable=False)
    subreddit = Column(String(100), nullable=False)
    title = Column(Text, nullable=False)
    selftext = Column(Text)
    author = Column(String(100))
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    created_utc = Column(DateTime, nullable=False)
    url = Column(Text)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"
    id = Column(Integer, primary_key=True)
    source_type = Column(String(20), nullable=False)
    source_id = Column(String(255), nullable=False)
    coin = Column(String(10), nullable=False)
    text_content = Column(Text, nullable=False)
    sentiment_label = Column(String(20), nullable=False)
    sentiment_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    model_used = Column(String(50), nullable=False)
    analyzed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    coin = Column(String(10), nullable=False)
    signal_type = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False)
    generated_at = Column(DateTime, nullable=False)
    sentiment_score = Column(Float)
    prediction_score = Column(Float)
    onchain_score = Column(Float)
    technical_score = Column(Float)
    divergence_signal = Column(String(30))
    reasoning = Column(Text, nullable=False)
    price_at_signal = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
