-- Initialize all tables for crypto-sentinel

-- Raw Reddit posts
CREATE TABLE IF NOT EXISTS reddit_posts (
    id SERIAL PRIMARY KEY,
    post_id VARCHAR(20) UNIQUE NOT NULL,
    subreddit VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    selftext TEXT,
    author VARCHAR(100),
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    created_utc TIMESTAMP NOT NULL,
    url TEXT,
    coin_mentions TEXT[],
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- Raw Reddit comments
CREATE TABLE IF NOT EXISTS reddit_comments (
    id SERIAL PRIMARY KEY,
    comment_id VARCHAR(20) UNIQUE NOT NULL,
    post_id VARCHAR(20) REFERENCES reddit_posts(post_id),
    body TEXT NOT NULL,
    author VARCHAR(100),
    score INTEGER DEFAULT 0,
    created_utc TIMESTAMP NOT NULL,
    coin_mentions TEXT[],
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- Raw news articles
CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    article_id VARCHAR(255) UNIQUE NOT NULL,
    source_name VARCHAR(200),
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    url TEXT,
    published_at TIMESTAMP NOT NULL,
    coin_mentions TEXT[],
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- Sentiment scores
CREATE TABLE IF NOT EXISTS sentiment_scores (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(20) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    coin VARCHAR(10) NOT NULL,
    text_content TEXT NOT NULL,
    sentiment_label VARCHAR(20) NOT NULL,
    sentiment_score FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    model_used VARCHAR(50) NOT NULL,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_type, source_id, coin)
);

-- Aggregated sentiment (per coin per time window)
CREATE TABLE IF NOT EXISTS sentiment_aggregated (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    window_size VARCHAR(10) NOT NULL,
    avg_sentiment FLOAT NOT NULL,
    median_sentiment FLOAT NOT NULL,
    sentiment_std FLOAT NOT NULL,
    bullish_count INTEGER NOT NULL,
    bearish_count INTEGER NOT NULL,
    neutral_count INTEGER NOT NULL,
    fud_count INTEGER NOT NULL,
    total_posts INTEGER NOT NULL,
    sentiment_velocity FLOAT,
    sentiment_acceleration FLOAT,
    dominant_narratives TEXT[],
    social_volume INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(coin, window_start, window_size)
);

-- Price data (OHLCV)
CREATE TABLE IF NOT EXISTS price_data (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    volume FLOAT NOT NULL,
    quote_volume FLOAT,
    num_trades INTEGER,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(coin, timestamp, interval)
);

-- Technical indicators (computed)
CREATE TABLE IF NOT EXISTS technical_indicators (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    interval VARCHAR(10) NOT NULL,
    rsi FLOAT,
    macd FLOAT,
    macd_signal FLOAT,
    macd_histogram FLOAT,
    bb_upper FLOAT,
    bb_middle FLOAT,
    bb_lower FLOAT,
    bb_bandwidth FLOAT,
    atr FLOAT,
    obv FLOAT,
    ema_12 FLOAT,
    ema_26 FLOAT,
    sma_50 FLOAT,
    sma_200 FLOAT,
    volume_sma_20 FLOAT,
    volume_ratio FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(coin, timestamp, interval)
);

-- On-chain data (whale transactions)
CREATE TABLE IF NOT EXISTS whale_transactions (
    id SERIAL PRIMARY KEY,
    tx_hash VARCHAR(100) UNIQUE NOT NULL,
    blockchain VARCHAR(20) NOT NULL,
    from_address VARCHAR(100),
    to_address VARCHAR(100),
    value_usd FLOAT NOT NULL,
    value_native FLOAT NOT NULL,
    token_symbol VARCHAR(20),
    block_number BIGINT,
    timestamp TIMESTAMP NOT NULL,
    tx_type VARCHAR(20),
    is_exchange_from BOOLEAN DEFAULT FALSE,
    is_exchange_to BOOLEAN DEFAULT FALSE,
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- On-chain aggregated metrics
CREATE TABLE IF NOT EXISTS onchain_metrics (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    window_size VARCHAR(10) NOT NULL,
    whale_tx_count INTEGER NOT NULL,
    whale_volume_usd FLOAT NOT NULL,
    exchange_inflow_usd FLOAT NOT NULL,
    exchange_outflow_usd FLOAT NOT NULL,
    net_flow_usd FLOAT NOT NULL,
    large_tx_count INTEGER NOT NULL,
    whale_activity_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(coin, timestamp, window_size)
);

-- Model predictions
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    predicted_at TIMESTAMP NOT NULL,
    horizon_hours INTEGER NOT NULL,
    predicted_direction VARCHAR(10) NOT NULL,
    confidence FLOAT NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    predicted_price_change_pct FLOAT,
    features_used TEXT,
    actual_direction VARCHAR(10),
    actual_price_change_pct FLOAT,
    was_correct BOOLEAN,
    outcome_recorded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Trading signals
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    generated_at TIMESTAMP NOT NULL,
    sentiment_score FLOAT,
    prediction_score FLOAT,
    onchain_score FLOAT,
    technical_score FLOAT,
    divergence_signal VARCHAR(30),
    reasoning TEXT NOT NULL,
    price_at_signal FLOAT,
    price_after_1h FLOAT,
    price_after_4h FLOAT,
    price_after_24h FLOAT,
    outcome VARCHAR(20),
    pnl_pct FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Fear & Greed Index history
CREATE TABLE IF NOT EXISTS fear_greed_index (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    index_value INTEGER NOT NULL,
    label VARCHAR(20) NOT NULL,
    sentiment_component FLOAT NOT NULL,
    social_volume_component FLOAT NOT NULL,
    volume_momentum_component FLOAT NOT NULL,
    volatility_component FLOAT NOT NULL,
    whale_activity_component FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(timestamp)
);

-- Backtest results
CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) NOT NULL,
    coin VARCHAR(10) NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    initial_capital FLOAT NOT NULL,
    final_capital FLOAT NOT NULL,
    total_return_pct FLOAT NOT NULL,
    sharpe_ratio FLOAT,
    max_drawdown_pct FLOAT,
    win_rate FLOAT,
    total_trades INTEGER,
    profit_factor FLOAT,
    avg_win_pct FLOAT,
    avg_loss_pct FLOAT,
    equity_curve_json TEXT,
    trades_json TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Paper trading positions
CREATE TABLE IF NOT EXISTS paper_trades (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    quantity FLOAT NOT NULL,
    entry_price FLOAT NOT NULL,
    exit_price FLOAT,
    signal_id INTEGER REFERENCES signals(id),
    confidence FLOAT,
    pnl FLOAT,
    pnl_pct FLOAT,
    status VARCHAR(20) DEFAULT 'OPEN',
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LLM generated reports
CREATE TABLE IF NOT EXISTS market_reports (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(10),
    report_type VARCHAR(30) NOT NULL,
    report_text TEXT NOT NULL,
    model_used VARCHAR(50) NOT NULL,
    input_data_json TEXT,
    generated_at TIMESTAMP DEFAULT NOW()
);

-- Model performance tracking
CREATE TABLE IF NOT EXISTS model_performance (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    coin VARCHAR(10) NOT NULL,
    horizon_hours INTEGER NOT NULL,
    evaluation_date DATE NOT NULL,
    accuracy FLOAT,
    precision_score FLOAT,
    recall_score FLOAT,
    f1_score FLOAT,
    total_predictions INTEGER,
    correct_predictions INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(model_name, coin, horizon_hours, evaluation_date)
);

-- Narrative tracking
CREATE TABLE IF NOT EXISTS narrative_tracking (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    coin VARCHAR(10),
    narrative VARCHAR(100) NOT NULL,
    mention_count INTEGER NOT NULL,
    sentiment_avg FLOAT,
    source_type VARCHAR(20) NOT NULL,
    window_size VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_price_coin_ts ON price_data(coin, timestamp);
CREATE INDEX IF NOT EXISTS idx_sentiment_coin_ts ON sentiment_scores(coin, analyzed_at);
CREATE INDEX IF NOT EXISTS idx_sentiment_agg_coin_ts ON sentiment_aggregated(coin, window_start);
CREATE INDEX IF NOT EXISTS idx_signals_coin_ts ON signals(coin, generated_at);
CREATE INDEX IF NOT EXISTS idx_predictions_coin_ts ON predictions(coin, predicted_at);
CREATE INDEX IF NOT EXISTS idx_whale_ts ON whale_transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_fg_ts ON fear_greed_index(timestamp);
