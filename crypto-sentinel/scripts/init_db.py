"""
scripts/init_db.py — Create ALL tables and seed comprehensive demo data.
Run: python scripts/init_db.py
Creates every table referenced by every dashboard page.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json, random
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from database.connection import get_engine

engine = get_engine()
rng = random.Random(42)
now = datetime.utcnow()

# ─── Helpers ─────────────────────────────────────────────────────────────────
def ts(offset_hours=0):
    return (now - timedelta(hours=offset_hours)).strftime('%Y-%m-%d %H:%M:%S')

def ts_m(offset_minutes=0):
    return (now - timedelta(minutes=offset_minutes)).strftime('%Y-%m-%d %H:%M:%S')

# ─── ALL TABLE DDL ────────────────────────────────────────────────────────────
DDL = [
    # price_data
    """CREATE TABLE IF NOT EXISTS price_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, interval TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        UNIQUE(coin, interval, timestamp)
    )""",

    # sentiment_scores
    """CREATE TABLE IF NOT EXISTS sentiment_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL, source_id TEXT NOT NULL,
        coin TEXT NOT NULL, text_content TEXT NOT NULL,
        sentiment_label TEXT NOT NULL, sentiment_score REAL NOT NULL,
        confidence REAL NOT NULL, model_used TEXT NOT NULL,
        analyzed_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
        UNIQUE(source_type, source_id, coin)
    )""",

    # sentiment_aggregated — all columns needed by all pages
    """CREATE TABLE IF NOT EXISTS sentiment_aggregated (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, window_size TEXT NOT NULL,
        window_start TEXT NOT NULL,
        avg_sentiment REAL NOT NULL,
        sample_count INTEGER DEFAULT 0,
        bullish_count INTEGER DEFAULT 0,
        bearish_count INTEGER DEFAULT 0,
        neutral_count INTEGER DEFAULT 0,
        fud_count INTEGER DEFAULT 0,
        total_posts INTEGER DEFAULT 0,
        sentiment_velocity REAL DEFAULT 0.0,
        social_volume REAL DEFAULT 0.0,
        UNIQUE(coin, window_size, window_start)
    )""",

    # signals — with all columns needed by signals_alerts.py
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

    # news_articles — article_id is MD5 of title for dedup; sentiment cols for UI
    """CREATE TABLE IF NOT EXISTS news_articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id TEXT UNIQUE,
        source TEXT NOT NULL, title TEXT NOT NULL,
        url TEXT, content TEXT, coin TEXT,
        sentiment_label TEXT,
        sentiment_score REAL,
        published_at TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    # reddit_posts
    """CREATE TABLE IF NOT EXISTS reddit_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id TEXT UNIQUE NOT NULL, subreddit TEXT NOT NULL,
        title TEXT NOT NULL, selftext TEXT, author TEXT,
        score INTEGER DEFAULT 0, num_comments INTEGER DEFAULT 0,
        created_utc TEXT NOT NULL, url TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    # whale_transactions — all columns needed by onchain_intelligence.py
    """CREATE TABLE IF NOT EXISTS whale_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, token_symbol TEXT,
        tx_hash TEXT UNIQUE,
        from_address TEXT, to_address TEXT,
        value_usd REAL, direction TEXT,
        tx_type TEXT,
        is_exchange_from INTEGER DEFAULT 0,
        is_exchange_to INTEGER DEFAULT 0,
        block_time TEXT,
        fetched_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    # onchain_metrics — all columns needed by fear_greed, signal generator, onchain page
    """CREATE TABLE IF NOT EXISTS onchain_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, window_size TEXT DEFAULT '4h',
        timestamp TEXT NOT NULL,
        exchange_inflow_usd REAL DEFAULT 0,
        exchange_outflow_usd REAL DEFAULT 0,
        net_flow_usd REAL DEFAULT 0,
        whale_tx_count INTEGER DEFAULT 0,
        whale_volume_usd REAL DEFAULT 0,
        whale_activity_score REAL DEFAULT 0.5,
        UNIQUE(coin, window_size, timestamp)
    )""",

    # technical_indicators — all columns used by price_technicals, signal_generator
    """CREATE TABLE IF NOT EXISTS technical_indicators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, interval TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        rsi REAL, macd REAL, macd_signal REAL, macd_histogram REAL,
        bb_upper REAL, bb_middle REAL, bb_lower REAL, atr REAL,
        obv REAL,
        UNIQUE(coin, interval, timestamp)
    )""",

    # model_accuracy
    """CREATE TABLE IF NOT EXISTS model_accuracy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, model_name TEXT NOT NULL,
        accuracy REAL, precision REAL, recall REAL, f1_score REAL,
        sharpe REAL, horizon_h INTEGER DEFAULT 1,
        evaluated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    # predictions — needed by ai_predictions, model_performance, accuracy_tracker
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

    # narrative_tracking — needed by sentiment_analysis.py
    """CREATE TABLE IF NOT EXISTS narrative_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT NOT NULL, narrative TEXT NOT NULL,
        source_type TEXT NOT NULL, mention_count INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL
    )""",

    # fear_greed_index — needed by ai_reports, fear_greed_index.py
    """CREATE TABLE IF NOT EXISTS fear_greed_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        index_value INTEGER NOT NULL,
        label TEXT NOT NULL,
        sentiment_component REAL, social_volume_component REAL,
        volume_momentum_component REAL, volatility_component REAL,
        whale_activity_component REAL
    )""",

    # market_reports — needed by ai_reports.py
    """CREATE TABLE IF NOT EXISTS market_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coin TEXT, report_type TEXT NOT NULL,
        report_text TEXT NOT NULL, model_used TEXT,
        input_data_json TEXT,
        generated_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
    )""",

    # backtest_results — needed by backtester.py
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
]

# Tables that need column changes — drop and recreate
TABLES_TO_DROP = [
    "sentiment_aggregated", "signals", "whale_transactions",
    "news_articles", "sentiment_scores",
]
with engine.connect() as conn:
    for tbl in TABLES_TO_DROP:
        conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
    for stmt in DDL:
        conn.execute(text(stmt))
    conn.commit()
print("All tables created.")

# ─── SEED DATA ────────────────────────────────────────────────────────────────
COINS = {
    "BTC":  {"price": 83200, "trend": 0.68, "rsi": 54.2},
    "ETH":  {"price": 1910,  "trend": 0.61, "rsi": 49.8},
    "SOL":  {"price": 117,   "trend": 0.72, "rsi": 62.1},
    "XRP":  {"price": 2.14,  "trend": 0.44, "rsi": 45.5},
    "DOGE": {"price": 0.163, "trend": 0.38, "rsi": 38.7},
}

SIGNALS_SEED = [
    ("BTC",  "STRONG_BUY",  0.87, 0.91, 0.82, 0.79, 0.84,  0,
     '[\"LLM: BTC ETF inflow $1.3B — institutional FOMO\", \"ML: 3-day ascending triangle breakout detected\", \"On-chain: whale net outflow 2400 BTC (accumulation)\", \"RSI=54 momentum building\"]'),
    ("ETH",  "BUY",         0.74, 0.78, 0.71, 0.65, 0.72, 20,
     '[\"LLM: Dencun upgrade fuels L2 optimism\", \"ML: Support held at $1880 twice — bullish base\", \"On-chain: Staking deposits up 12% this week\"]'),
    ("SOL",  "STRONG_BUY",  0.82, 0.88, 0.79, 0.76, 0.81, 40,
     '[\"LLM: Solana DEX volume hits $3B/day record\", \"ML: Golden cross on 4h confirmed\", \"On-chain: NFT+DeFi TVL expanding rapidly\"]'),
    ("XRP",  "HOLD",        0.51, 0.52, 0.48, 0.55, 0.50, 60,
     '[\"LLM: SEC ruling uncertainty keeps sentiment neutral\", \"ML: Price coiling in tight range $2.10-$2.20\", \"On-chain: Mixed whale signals\"]'),
    ("DOGE", "SELL",        0.34, 0.32, 0.31, 0.38, 0.35, 80,
     '[\"LLM: Meme cycle cooling, retail interest waning\", \"ML: Death cross forming on daily\", \"On-chain: Large holder distribution detected\"]'),
    ("BTC",  "BUY",         0.71, 0.75, 0.68, 0.70, 0.68, 100,
     '[\"LLM: Halvening narrative driving media coverage\", \"ML: 50 EMA held as support on retest\", \"Volume spike on hourly = accumulation\"]'),
    ("ETH",  "STRONG_BUY",  0.84, 0.89, 0.81, 0.77, 0.83, 120,
     '[\"LLM: BlackRock ETH ETF rumor gaining traction\", \"ML: Bullish engulfing on daily chart\", \"On-chain: Exchange reserve 6-month low\"]'),
]

with engine.connect() as conn:
    # ── Signals ───────────────────────────────────────────────────────────────
    for coin, stype, conf, sent, pred, onc, tec, offset_min, reason in SIGNALS_SEED:
        price = COINS[coin]["price"] * rng.uniform(0.98, 1.02)
        conn.execute(text("""
            INSERT OR IGNORE INTO signals
              (coin,signal_type,confidence,generated_at,
               sentiment_score,prediction_score,onchain_score,technical_score,
               divergence_signal,reasoning,price_at_signal)
            VALUES(:c,:s,:conf,:ts,:sent,:pred,:onc,:tec,'NONE',:r,:p)
        """), {"c":coin,"s":stype,"conf":conf,"ts":ts_m(offset_min),
               "sent":sent,"pred":pred,"onc":onc,"tec":tec,"r":reason,"p":round(price,4)})

    # ── Sentiment aggregated (with all columns) ───────────────────────────────
    for coin, info in COINS.items():
        base = info["trend"]
        for h in range(24):
            t = (now - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
            ts_str = t.strftime('%Y-%m-%d %H:%M:%S')
            v = max(0.0, min(1.0, base + rng.gauss(0, 0.08)))
            total = rng.randint(5, 30)
            bullish = int(total * max(0, v - 0.1))
            bearish = int(total * max(0, 0.9 - v))
            neutral = max(0, total - bullish - bearish - rng.randint(0,2))
            fud = max(0, total - bullish - bearish - neutral)
            velocity = rng.gauss(0, 0.01)
            for wsize in ('1h', '4h'):
                conn.execute(text("""
                    INSERT OR IGNORE INTO sentiment_aggregated
                      (coin,window_size,window_start,avg_sentiment,sample_count,
                       bullish_count,bearish_count,neutral_count,fud_count,
                       total_posts,sentiment_velocity,social_volume)
                    VALUES(:c,:ws,:ts,:v,:n,:b,:be,:ne,:f,:tp,:vel,:sv)
                """), {"c":coin,"ws":wsize,"ts":ts_str,"v":round(v,3),"n":total,
                       "b":bullish,"be":bearish,"ne":neutral,"f":fud,
                       "tp":total,"vel":round(velocity,4),"sv":float(total*12)})

    # ── Price data (48h of 15m candles + 1h candles) ─────────────────────────
    for coin, info in COINS.items():
        p = info["price"]
        for m in range(192):  # 48h * 4
            t_str = (now - timedelta(minutes=m*15)).strftime('%Y-%m-%d %H:%M:%S')
            o = p * rng.uniform(0.9985, 1.0015)
            c = o * rng.uniform(0.998, 1.002)
            h = max(o,c)*rng.uniform(1.0, 1.002)
            l = min(o,c)*rng.uniform(0.998, 1.0)
            vol = p * rng.uniform(3000, 12000)
            for interval in ('15m', '1h'):
                conn.execute(text("""
                    INSERT OR IGNORE INTO price_data
                      (coin,interval,timestamp,open,high,low,close,volume)
                    VALUES(:c,:i,:t,:o,:h,:l,:cl,:v)
                """), {"c":coin,"i":interval,"t":t_str,
                       "o":round(o,4),"h":round(h,4),"l":round(l,4),"cl":round(c,4),"v":round(vol,2)})
            p = c

    # ── Technical indicators ───────────────────────────────────────────────────
    for coin, info in COINS.items():
        rsi_base = info["rsi"]
        price_base = info["price"]
        for h in range(48):
            t_str = (now - timedelta(hours=h)).strftime('%Y-%m-%d %H:%M:%S')
            rsi_val = max(10, min(90, rsi_base + rng.gauss(0, 3)))
            macd_val = rng.gauss(0, price_base * 0.001)
            macd_sig = macd_val * rng.uniform(0.8, 1.2)
            macd_hist = macd_val - macd_sig
            bb_mid = price_base * rng.uniform(0.995, 1.005)
            bb_std = price_base * 0.015
            conn.execute(text("""
                INSERT OR IGNORE INTO technical_indicators
                  (coin,interval,timestamp,rsi,macd,macd_signal,macd_histogram,
                   bb_upper,bb_middle,bb_lower,atr)
                VALUES(:c,'1h',:t,:rsi,:macd,:ms,:mh,:bu,:bm,:bl,:atr)
            """), {"c":coin,"t":t_str,"rsi":round(rsi_val,2),
                   "macd":round(macd_val,4),"ms":round(macd_sig,4),"mh":round(macd_hist,4),
                   "bu":round(bb_mid+bb_std*2,4),"bm":round(bb_mid,4),"bl":round(bb_mid-bb_std*2,4),
                   "atr":round(price_base*0.01,4)})

    # ── Onchain metrics ───────────────────────────────────────────────────────
    for coin in ("BTC","ETH"):
        price_base = COINS[coin]["price"]
        trend = COINS[coin]["trend"]
        for h in range(42):
            t_str = (now - timedelta(hours=h*4)).strftime('%Y-%m-%d %H:%M:%S')
            inflow = rng.uniform(10e6, 80e6)
            outflow = rng.uniform(15e6, 90e6) if trend > 0.55 else rng.uniform(5e6, 40e6)
            net = outflow - inflow
            score = min(1.0, max(0.0, 0.5 + net/100e6))
            conn.execute(text("""
                INSERT OR IGNORE INTO onchain_metrics
                  (coin,window_size,timestamp,exchange_inflow_usd,exchange_outflow_usd,
                   net_flow_usd,whale_tx_count,whale_volume_usd,whale_activity_score)
                VALUES(:c,'4h',:t,:i,:o,:n,:wc,:wv,:ws)
            """), {"c":coin,"t":t_str,"i":round(inflow,2),"o":round(outflow,2),
                   "n":round(net,2),"wc":rng.randint(3,25),
                   "wv":round(rng.uniform(5e6,50e6),2),"ws":round(score,3)})

    # ── Whale transactions ─────────────────────────────────────────────────────
    tx_types = ["exchange_inflow","exchange_outflow","transfer"]
    for coin in ("BTC","ETH"):
        for i in range(15):
            t_str = (now - timedelta(hours=i*2+rng.randint(0,3))).strftime('%Y-%m-%d %H:%M:%S')
            ttype = rng.choice(tx_types)
            val = rng.uniform(800000, 25000000)
            conn.execute(text("""
                INSERT OR IGNORE INTO whale_transactions
                  (coin,token_symbol,tx_hash,from_address,to_address,
                   value_usd,direction,tx_type,is_exchange_from,is_exchange_to,block_time)
                VALUES(:c,:ts,:h,:fa,:ta,:v,:d,:tt,:ief,:iet,:bt)
            """), {"c":coin,"ts":coin,"h":f"0x{rng.randint(10**15,10**16-1):016x}",
                   "fa":f"0x{rng.randint(10**15,10**16-1):016x}",
                   "ta":f"0x{rng.randint(10**15,10**16-1):016x}",
                   "v":round(val,2),"d":"outflow" if "outflow" in ttype else "inflow",
                   "tt":ttype,
                   "ief":1 if "inflow"  in ttype else 0,
                   "iet":1 if "outflow" in ttype else 0,
                   "bt":t_str})

    # ── Predictions ───────────────────────────────────────────────────────────
    directions = ["UP","DOWN"]
    models = ["ensemble","xgboost","lstm"]
    for coin in COINS:
        for i in range(20):
            t_str = (now - timedelta(hours=i*3)).strftime('%Y-%m-%d %H:%M:%S')
            pred_dir = rng.choice(directions)
            conf = rng.uniform(0.52, 0.82)
            # Older predictions have outcomes
            if i > 4:
                actual = rng.choice(directions)
                correct = 1 if actual == pred_dir else 0
                outcome_ts = (now - timedelta(hours=i*3-4)).strftime('%Y-%m-%d %H:%M:%S')
            else:
                actual, correct, outcome_ts = None, None, None
            conn.execute(text("""
                INSERT OR IGNORE INTO predictions
                  (coin,model_name,horizon_hours,predicted_at,predicted_direction,
                   confidence,actual_direction,was_correct,outcome_recorded_at)
                VALUES(:c,:m,4,:t,:pd,:conf,:ad,:wc,:ot)
            """), {"c":coin,"m":rng.choice(models),"t":t_str,"pd":pred_dir,
                   "conf":round(conf,4),"ad":actual,"wc":correct,"ot":outcome_ts})

    # ── Narrative tracking ─────────────────────────────────────────────────────
    narratives_btc = ["ETF inflow","halving","BlackRock","SEC approval","institutional buying",
                      "MicroStrategy","whale accumulation","bull run","Fed pivot","BTC dominance"]
    narratives_eth = ["Dencun upgrade","L2 scaling","staking","DeFi TVL","ETH ETF","EIP-4844"]
    narratives_sol = ["DEX volume","Firedancer","NFT boom","DePIN","Solana ETF"]
    narratives_map = {"BTC":narratives_btc,"ETH":narratives_eth,"SOL":narratives_sol,
                      "XRP":["SEC ruling","Ripple","CBDC","payment rails"],
                      "DOGE":["Elon tweet","meme cycle","whale dump","retail exodus"]}
    for coin, narrs in narratives_map.items():
        for narr in narrs:
            for h in range(6):
                t_str = (now - timedelta(hours=h*4)).strftime('%Y-%m-%d %H:%M:%S')
                count = rng.randint(2, 45)
                for src in ("reddit","news"):
                    conn.execute(text("""
                        INSERT OR IGNORE INTO narrative_tracking
                          (coin,narrative,source_type,mention_count,timestamp)
                        VALUES(:c,:n,:s,:mc,:t)
                    """), {"c":coin,"n":narr,"s":src,"mc":count,"t":t_str})

    # ── Fear & Greed index ─────────────────────────────────────────────────────
    fg_labels = [(0,25,"Extreme Fear"),(25,45,"Fear"),(45,55,"Neutral"),(55,75,"Greed"),(75,100,"Extreme Greed")]
    for h in range(48):
        t_str = (now - timedelta(hours=h)).strftime('%Y-%m-%d %H:%M:%S')
        val = max(0, min(100, int(55 + rng.gauss(0, 15))))
        label = next((l for lo,hi,l in fg_labels if lo<=val<hi), "Neutral")
        conn.execute(text("""
            INSERT OR IGNORE INTO fear_greed_index
              (timestamp,index_value,label,sentiment_component,social_volume_component,
               volume_momentum_component,volatility_component,whale_activity_component)
            VALUES(:t,:iv,:l,:sc,:svc,:vmc,:vc,:wac)
        """), {"t":t_str,"iv":val,"l":label,
               "sc":round(rng.uniform(0.45,0.75),3),"svc":round(rng.uniform(0.4,0.7),3),
               "vmc":round(rng.uniform(0.45,0.65),3),"vc":round(rng.uniform(0.5,0.7),3),
               "wac":round(rng.uniform(0.4,0.8),3)})

    # ── Model accuracy ─────────────────────────────────────────────────────────
    for coin in COINS:
        for mname in ("XGBoost","LSTM","AutoGluon","Ensemble"):
            conn.execute(text("""
                INSERT OR IGNORE INTO model_accuracy
                  (coin,model_name,accuracy,precision,recall,f1_score,sharpe,horizon_h)
                VALUES(:c,:m,:a,:p,:r,:f,:s,1)
            """), {"c":coin,"m":mname,"a":round(rng.uniform(0.56,0.72),3),
                   "p":round(rng.uniform(0.54,0.70),3),"r":round(rng.uniform(0.52,0.68),3),
                   "f":round(rng.uniform(0.53,0.69),3),"s":round(rng.uniform(0.8,2.1),2)})

    # ── Market reports ─────────────────────────────────────────────────────────
    sample_reports = [
        ("BTC","coin_analysis","Bitcoin shows strong accumulation patterns with ETF inflows reaching $1.3B daily. On-chain metrics suggest whale activity is bullish. Technical indicators point to a potential breakout above $85,000. RECOMMENDATION: BUY"),
        ("ETH","coin_analysis","Ethereum's Dencun upgrade has significantly reduced L2 transaction costs, driving ecosystem growth. Exchange reserves hit a 6-month low — a classic accumulation signal. RECOMMENDATION: BUY"),
        (None,"market_overview","Overall crypto market sentiment is shifting to Greed (F&G: 68). Bitcoin dominance at 54% suggests altcoin rotation may be near. Key catalysts: Fed rate decision this week, ETH ETF rumor."),
    ]
    for coin, rtype, text_content in sample_reports:
        conn.execute(text("""
            INSERT OR IGNORE INTO market_reports (coin,report_type,report_text,model_used)
            VALUES(:c,:r,:t,'mistral-7b-demo')
        """), {"c":coin,"r":rtype,"t":text_content})

    # ── News articles ──────────────────────────────────────────────────────────
    import hashlib as _hl
    news = [
        ("CoinDesk",  "BTC", "Bitcoin ETF sees record $1.3B daily inflow as institutions pile in",       "BULLISH", 0.92),
        ("CoinTelegraph","ETH","Ethereum Dencun upgrade reduces L2 fees by 90%, adoption surges",         "BULLISH", 0.87),
        ("The Block",  "SOL", "Solana DEX volume surpasses Ethereum for third consecutive week",           "BULLISH", 0.83),
        ("Crypto Briefing","XRP","XRP price stalls as market awaits SEC ruling outcome",                    "NEUTRAL", 0.51),
        ("Google News","DOGE","Dogecoin whale moves 500M DOGE to exchange — sell pressure incoming",       "BEARISH", 0.26),
        ("CoinDesk",  "BTC", "MicroStrategy adds 2,000 BTC as Bitcoin ETF demand surges",                 "BULLISH", 0.89),
        ("CoinTelegraph","ETH","BlackRock files for spot Ethereum ETF — report",                            "BULLISH", 0.91),
        ("The Block",  "BTC", "Fed signals rate hold — risk assets including crypto may benefit",           "BULLISH", 0.72),
        ("Crypto Briefing","SOL","Solana staking rewards hit 8% APY amid validator growth boom",           "BULLISH", 0.80),
        ("Google News","BTC", "Bitcoin halvening in 15 days — historical patterns show 6-month bull runs", "BULLISH", 0.88),
    ]
    for i, (src, coin, title, slabel, sscore) in enumerate(news):
        t_str = (now - timedelta(hours=i*3)).strftime('%Y-%m-%d %H:%M:%S')
        aid   = _hl.md5(title.encode()).hexdigest()[:32]
        conn.execute(text("""
            INSERT OR IGNORE INTO news_articles
              (article_id,source,title,coin,published_at,sentiment_label,sentiment_score)
            VALUES(:aid,:s,:t,:c,:ts,:sl,:ss)
        """), {"aid":aid,"s":src,"t":title,"c":coin,"ts":t_str,"sl":slabel,"ss":sscore})

    conn.commit()

print("Demo data seeded successfully.")
print(f"DB location: {engine.url}")

# Quick row-count verification
import pandas as pd
tables = ["signals","sentiment_aggregated","price_data","technical_indicators",
          "onchain_metrics","predictions","narrative_tracking","fear_greed_index",
          "whale_transactions","news_articles","market_reports","model_accuracy"]
for tbl in tables:
    try:
        cnt = pd.read_sql(f"SELECT COUNT(*) as c FROM {tbl}", engine).iloc[0]["c"]
        print(f"  {tbl:30s}: {cnt} rows")
    except Exception as e:
        print(f"  {tbl:30s}: ERROR — {e}")
