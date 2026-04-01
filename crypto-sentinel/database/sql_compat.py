"""
database/sql_compat.py — SQLite SQL helper functions.

Provides helpers for dynamic time comparison and timestamp bucketing
using SQLite-native syntax:
  time_ago(hours=N)         →  ISO timestamp string for bind params
  hour_bucket_sql(col)      →  strftime('%Y-%m-%d %H:00:00', col)
"""
from datetime import datetime, timedelta, timezone


def time_ago(hours=0, days=0, minutes=0) -> str:
    """Return ISO timestamp string for 'now minus given offset', for use as a bind param."""
    delta = timedelta(hours=hours, days=days, minutes=minutes)
    return (datetime.now(timezone.utc) - delta).strftime('%Y-%m-%d %H:%M:%S')


def hour_bucket_sql(col: str) -> str:
    """SQLite equivalent of date_trunc('hour', col)."""
    return f"strftime('%Y-%m-%d %H:00:00', {col})"
