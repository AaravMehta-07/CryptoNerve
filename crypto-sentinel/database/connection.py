"""
Database engine — lazy singleton (SQLite only).

Uses StaticPool so threads share a single connection safely.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from loguru import logger
from config.settings import settings

_engine = None


def get_engine():
    """Return a shared SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        # Ensure data/ directory exists
        db_path = url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        logger.debug(f"SQLAlchemy engine initialised: {url[:60]}...")
    return _engine


def get_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db():
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_connection():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
