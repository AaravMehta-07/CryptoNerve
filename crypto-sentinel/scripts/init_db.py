"""
scripts/init_db.py — Create ALL tables (schema only, no demo data).
Run: python scripts/init_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.connection import get_engine

engine = get_engine()

# ─── ALL TABLE DDL ────────────────────────────────────────────────────────────
DDL = [
    """CREATE TABLE IF NOT EXISTS price_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, interval TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        UNIQUE(coin, interval, timestamp)
    )""",

    """CREATE TABLE IF NOT EXISTS sentiment_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL, source_id TEXT NOT NULL,
        coin TEXT NOT NULL, text_content TEXT NOT NULL,
        sentiment_label TEXT NOT NULL, sentiment_score REAL NOT NULL,
        confidence REAL NOT NULL, model_used TEXT NOT NULL,
        analyzed_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
        UNIQUE(source_type, source_id, coin)
    )""",

    """CREATE TABLE IF NOT EXISTS sentiment_aggregated (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, window_size TEXT NOT NULL,
        window_start TEXT NOT NULL,
        window_end TEXT,
        avg_sentiment REAL NOT NULL,
        median_sentiment REAL DEFAULT 0.0,
        sentiment_std REAL DEFAULT 0.0,
        sample_count INTEGER DEFAULT 0,
        bullish_count INTEGER DEFAULT 0,
        bearish_count INTEGER DEFAULT 0,
        neutral_count INTEGER DEFAULT 0,
        fud_count INTEGER DEFAULT 0,
        total_posts INTEGER DEFAULT 0,
        sentiment_velocity REAL DEFAULT 0.0,
        sentiment_acceleration REAL DEFAULT 0.0,
        dominant_narratives TEXT,
        social_volume REAL DEFAULT 0.0,
        UNIQUE(coin, window_size, window_start)
    )""",

    """CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, signal_type TEXT NOT NULL,
        confidence REAL NOT NULL,
        generated_at TEXT NOT NULL,
        sentiment_score REAL, prediction_score REAL,
        onchain_score REAL, technical_score REAL,
        divergence_signal TEXT,
        reasoning TEXT NOT NULL,
        price_at_signal REAL,
        created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS news_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id TEXT UNIQUE,
        source_name TEXT NOT NULL, title TEXT NOT NULL,
        description TEXT, content TEXT,
        url TEXT, coin TEXT,
        coin_mentions TEXT,
        sentiment_label TEXT,
        sentiment_score REAL,
        published_at TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS reddit_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id TEXT UNIQUE NOT NULL, subreddit TEXT NOT NULL,
        title TEXT NOT NULL, selftext TEXT, author TEXT,
        score INTEGER DEFAULT 0, num_comments INTEGER DEFAULT 0,
        created_utc TEXT NOT NULL, url TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS whale_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tx_hash TEXT UNIQUE,
        blockchain TEXT,
        coin TEXT, token_symbol TEXT,
        from_address TEXT, to_address TEXT,
        value_usd REAL, value_native REAL,
        direction TEXT, tx_type TEXT,
        block_number INTEGER,
        is_exchange_from INTEGER DEFAULT 0,
        is_exchange_to INTEGER DEFAULT 0,
        block_time TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS onchain_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, window_size TEXT DEFAULT '4h',
        timestamp TEXT NOT NULL,
        exchange_inflow_usd REAL DEFAULT 0,
        exchange_outflow_usd REAL DEFAULT 0,
        net_flow_usd REAL DEFAULT 0,
        whale_tx_count INTEGER DEFAULT 0,
        whale_volume_usd REAL DEFAULT 0,
        large_tx_count INTEGER DEFAULT 0,
        whale_activity_score REAL DEFAULT 0.5,
        UNIQUE(coin, window_size, timestamp)
    )""",

    """CREATE TABLE IF NOT EXISTS technical_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, interval TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        rsi REAL, macd REAL, macd_signal REAL, macd_histogram REAL,
        bb_upper REAL, bb_middle REAL, bb_lower REAL, atr REAL,
        obv REAL,
        UNIQUE(coin, interval, timestamp)
    )""",

    """CREATE TABLE IF NOT EXISTS model_accuracy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, model_name TEXT NOT NULL,
        accuracy REAL, precision REAL, recall REAL, f1_score REAL,
        sharpe REAL, horizon_h INTEGER DEFAULT 1,
        evaluated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, model_name TEXT NOT NULL,
        horizon_hours INTEGER NOT NULL,
        predicted_at TEXT NOT NULL,
        predicted_direction TEXT NOT NULL,
        confidence REAL NOT NULL,
        predicted_price_change_pct REAL,
        actual_direction TEXT,
        actual_price_change_pct REAL,
        was_correct INTEGER,
        features_used TEXT,
        outcome_recorded_at TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS narrative_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, narrative TEXT NOT NULL,
        source_type TEXT NOT NULL, mention_count INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS fear_greed_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        index_value INTEGER NOT NULL,
        label TEXT NOT NULL,
        sentiment_component REAL, social_volume_component REAL,
        volume_momentum_component REAL, volatility_component REAL,
        whale_activity_component REAL
    )""",

    """CREATE TABLE IF NOT EXISTS market_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT, report_type TEXT NOT NULL,
        report_text TEXT NOT NULL, model_used TEXT,
        input_data_json TEXT,
        generated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    """CREATE TABLE IF NOT EXISTS backtest_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT, coin TEXT, strategy_name TEXT,
        start_date TEXT, end_date TEXT,
        initial_capital REAL, final_capital REAL,
        total_return_pct REAL, sharpe_ratio REAL,
        max_drawdown_pct REAL, win_rate REAL,
        total_trades INTEGER, profit_factor REAL,
        avg_win_pct REAL, avg_loss_pct REAL,
        equity_curve_json TEXT, trades_json TEXT
    )""",

    # LOW-04 FIX: paper_trades table was missing — PaperTrader crashed on first use
    """CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL,
        action TEXT NOT NULL,
        quantity REAL NOT NULL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        signal_id INTEGER,
        confidence REAL DEFAULT 0.5,
        status TEXT NOT NULL DEFAULT 'OPEN',
        pnl REAL,
        pnl_pct REAL,
        opened_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
        closed_at TEXT
    )""",

    # LOW-05 FIX: model_performance table was missing — ModelTrainer._save_performance crashed
    """CREATE TABLE IF NOT EXISTS model_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_name TEXT NOT NULL,
        coin TEXT NOT NULL,
        horizon_hours INTEGER DEFAULT 1,
        evaluation_date TEXT NOT NULL,
        accuracy REAL,
        total_predictions INTEGER DEFAULT 0,
        correct_predictions INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",
]

# Drop tables that may have stale schemas from old runs, then recreate all
TABLES_TO_DROP = [
    "sentiment_aggregated", "signals", "whale_transactions",
    "news_articles", "sentiment_scores", "onchain_metrics",
]

with engine.connect() as conn:
    for tbl in TABLES_TO_DROP:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
    for stmt in DDL:
        conn.execute(text(stmt))
    conn.commit()

print("✅ All tables created (schema only, no demo data).")
print(f"   DB: {engine.url}")
