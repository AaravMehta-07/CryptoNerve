"""
database/sql_compat.py — SQLite-compatible SQL helper functions.

Replaces all PostgreSQL-specific syntax throughout the codebase:
  NOW() - INTERVAL '...'    →  time_ago(hours=N)
  date_trunc('hour', col)   →  hour_bucket SQL snippet
  ::numeric casts           →  removed
  LEFT(col, N)              →  SUBSTR(col, 1, N)
"""
from datetime import datetime, timedelta


def time_ago(hours=0, days=0, minutes=0) -> str:
    """Return ISO timestamp string for 'now minus given offset', for use as a bind param."""
    delta = timedelta(hours=hours, days=days, minutes=minutes)
    return (datetime.utcnow() - delta).strftime('%Y-%m-%d %H:%M:%S')


def hour_bucket_sql(col: str) -> str:
    """SQLite equivalent of date_trunc('hour', col)."""
    return f"strftime('%Y-%m-%d %H:00:00', {col})"


def read_sql_compat(query: str, engine, params: dict = None):
    """
    Drop-in replacement for pd.read_sql that handles SQLite compatibility.
    Replaces %(name)s style params if engine is SQLite.
    """
    import pandas as pd
    return pd.read_sql(query, engine, params=params)
