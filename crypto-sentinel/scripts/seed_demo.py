"""
scripts/seed_demo.py  — Populate ALL tables with rich hackathon demo data.
Matches EXACT schema from init_db.py.
Run: python scripts/seed_demo.py   (from crypto-sentinel/ directory)
"""
import sys, os, hashlib, random, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from sqlalchemy import text
from database.connection import get_engine

engine = get_engine()
rng = random.Random(42)
now = datetime.utcnow()

def ts(h=0):
    return (now - timedelta(hours=h)).strftime('%Y-%m-%d %H:%M:%S')

def uid(*a):
    return hashlib.md5("|".join(str(x) for x in a).encode()).hexdigest()[:32]

COINS = {
    "BTC":  {"price": 87_450.0,  "vol": 28_000,       "rsi": 54.2, "trend": 0.72},
    "ETH":  {"price": 2_031.0,   "vol": 95_000,       "rsi": 58.6, "trend": 0.64},
    "SOL":  {"price": 127.40,    "vol": 420_000,      "rsi": 61.3, "trend": 0.81},
    "XRP":  {"price": 2.187,     "vol": 12_000_000,   "rsi": 63.4, "trend": 0.88},
    "DOGE": {"price": 0.1623,    "vol": 85_000_000,   "rsi": 55.1, "trend": 0.62},
}

ARTICLES = [
    ("BTC","BULLISH",0.87,"Bitcoin surges past $87K as BlackRock ETF inflows hit record $1.2B single day","https://coindesk.com/btc-blackrock","CoinDesk"),
    ("BTC","BULLISH",0.82,"MicroStrategy adds 12,000 BTC — total holdings exceed 500,000 coins","https://cointelegraph.com/microstrategy","CoinTelegraph"),
    ("BTC","NEUTRAL",0.51,"Bitcoin hash rate hits all-time high 720 EH/s as miners prep for halving","https://decrypt.co/hashrate","Decrypt"),
    ("BTC","BULLISH",0.79,"Federal Reserve signals rate pause — crypto markets rally on macro relief","https://coindesk.com/fed-pause","CoinDesk"),
    ("BTC","BEARISH",0.22,"On-chain data shows 45,000 BTC moved to exchanges — selling pressure ahead?","https://cointelegraph.com/exchange-flow","CoinTelegraph"),
    ("ETH","BULLISH",0.84,"Ethereum staking yield rises to 4.8% — validator queue shrinks, institutional demand soars","https://coindesk.com/eth-staking","CoinDesk"),
    ("ETH","BULLISH",0.76,"EIP-7702 approved: Ethereum account abstraction ships in next hard fork","https://cointelegraph.com/eip7702","CoinTelegraph"),
    ("ETH","NEUTRAL",0.49,"Ethereum Layer 2 TVL reaches $58B — Base and Arbitrum lead expansion","https://decrypt.co/l2-tvl","Decrypt"),
    ("ETH","BEARISH",0.31,"Ethereum gas fees spike above 80 gwei during NFT mint frenzy","https://coindesk.com/eth-gas","CoinDesk"),
    ("SOL","BULLISH",0.89,"Solana surpasses Ethereum in daily DEX volume for 3rd consecutive week","https://cointelegraph.com/sol-dex","CoinTelegraph"),
    ("SOL","BULLISH",0.78,"Coinbase lists Solana futures — open interest surges 340% in first 24 hours","https://decrypt.co/sol-futures","Decrypt"),
    ("SOL","NEUTRAL",0.52,"Solana Foundation announces $100M developer grants for DeFi protocols","https://coindesk.com/sol-grants","CoinDesk"),
    ("SOL","FUD",0.12,"Jupiter DEX reports $2.8M exploit via oracle manipulation — patch in progress","https://cointelegraph.com/jupiter","CoinTelegraph"),
    ("XRP","BULLISH",0.91,"Ripple wins final judgment — XRP not a security, exchanges relist immediately","https://decrypt.co/ripple-ruling","Decrypt"),
    ("XRP","BULLISH",0.83,"Bank of America launches XRP cross-border settlement pilot with 12 banks","https://coindesk.com/boa-xrp","CoinDesk"),
    ("XRP","NEUTRAL",0.53,"XRP Ledger hits 1 billion transactions — Ripple highlights speed advantage","https://cointelegraph.com/xrp-1b","CoinTelegraph"),
    ("XRP","BEARISH",0.27,"Mt. Gox trustee moves $1.4B XRP to new wallet — distribution concerns resurface","https://decrypt.co/mtgox-xrp","Decrypt"),
    ("DOGE","BULLISH",0.77,"Elon Musk tweets 'The people's crypto 🐕' — DOGE surges 18% in 2 hours","https://coindesk.com/doge-musk","CoinDesk"),
    ("DOGE","BULLISH",0.71,"X (Twitter) files money transmitter licenses in all 50 US states — DOGE payment rampup","https://cointelegraph.com/x-licenses","CoinTelegraph"),
    ("DOGE","NEUTRAL",0.48,"Dogecoin Foundation releases DogeLabs utility roadmap — community divided","https://decrypt.co/doge-labs","Decrypt"),
    ("DOGE","FUD",0.14,"Large DOGE whale dumps 800M coins — tracker alerts fire across Discord","https://coindesk.com/doge-dump","CoinDesk"),
]

SIGNALS = [
    ("BTC","STRONG_BUY",0.91,87450,"LLM avg sentiment: 0.847 (BULLISH) | RSI: 54.2 | Whale: 0.78 | Composite: 0.821 → STRONG BUY — ETF inflows + macro relief + whale accumulation alignment"),
    ("BTC","BUY",0.78,85200,"LLM avg sentiment: 0.762 (BULLISH) | RSI: 62.1 | Whale: 0.65 | Composite: 0.734 → BUY — MicroStrategy accumulation + ascending triangle breakout"),
    ("BTC","HOLD",0.55,83100,"LLM avg sentiment: 0.511 (NEUTRAL) | RSI: 51.8 | Whale: 0.52 | Composite: 0.533 → HOLD — mixed signals, exchange inflow caution"),
    ("ETH","STRONG_BUY",0.86,2031,"LLM avg sentiment: 0.832 (BULLISH) | RSI: 49.2 | Whale: 0.79 | Composite: 0.808 → STRONG BUY — EIP-7702 + institutional staking flows"),
    ("ETH","BUY",0.75,1987,"LLM avg sentiment: 0.721 (BULLISH) | RSI: 52.1 | Whale: 0.63 | Composite: 0.698 → BUY — DeFi TVL growth + L2 expansion"),
    ("SOL","STRONG_BUY",0.93,127.4,"LLM avg sentiment: 0.881 (BULLISH) | RSI: 61.3 | Whale: 0.84 | Composite: 0.867 → STRONG BUY — DEX volume dominance + Coinbase futures listing"),
    ("SOL","SELL",0.68,134.2,"LLM avg sentiment: 0.318 (BEARISH) | RSI: 76.2 (OB) | Whale: 0.34 | Composite: 0.351 → SELL — overbought RSI + exploit FUD"),
    ("XRP","STRONG_BUY",0.94,2.187,"LLM avg sentiment: 0.912 (BULLISH) | RSI: 63.4 | Whale: 0.87 | Composite: 0.891 → STRONG BUY — legal clarity + banking integration"),
    ("XRP","HOLD",0.57,1.978,"LLM avg sentiment: 0.523 (NEUTRAL) | RSI: 52.8 | Whale: 0.51 | Composite: 0.541 → HOLD — Mt.Gox distribution overhang"),
    ("DOGE","BUY",0.78,0.1623,"LLM avg sentiment: 0.769 (BULLISH) | RSI: 59.1 | Whale: 0.69 | Composite: 0.741 → BUY — Elon tweet + X payments speculation"),
    ("DOGE","STRONG_BUY",0.85,0.1511,"LLM avg sentiment: 0.841 (BULLISH) | RSI: 48.7 | Whale: 0.78 | Composite: 0.812 → STRONG BUY — social spike + X platform integration"),
]

REPORTS = [
    ("BTC","market_analysis","mistral-7b-instruct-q3km",
     "Bitcoin Market Analysis\n\nBTC/USD trading at $87,450 (+3.2% 24h). Sentiment strongly bullish driven by record BlackRock ETF inflows and Fed rate pause.\n\nOn-Chain: Exchange reserves -2.1%, long-term holder supply at 14.7M BTC ATH, whale net accumulation +18,400 BTC this week.\n\nTechnicals: RSI 54.2 (neutral), MACD positive crossover on 4h, support $83,500 (200h EMA), resistance $92,000.\n\nSentiment: 0.847 BULLISH — 9/12 articles bullish, 2 neutral, 1 bearish.\n\nSignal: STRONG BUY | Confidence: 91.2%\nComposite 0.821 from ETF inflows + macro relief + whale accumulation."),
    ("ETH","market_analysis","mistral-7b-instruct-q3km",
     "Ethereum Market Analysis\n\nETH/USD $2,031 — consolidating after 5.4% weekly gain. Staking yield stabilises at 4.8%. EIP-7702 account abstraction approval is structural positive.\n\nOn-Chain: 34.2M ETH staked (28.4% supply), L2 TVL $58B (+12% MoM), burn 1,240 ETH/day, 23,000 ETH moved off exchanges this week.\n\nTechnicals: RSI 58.6, price riding upper Bollinger Band. Support $1,950, resistance $2,150.\n\nSentiment: 0.784 BULLISH — 8/10 articles bullish.\n\nSignal: BUY | Confidence: 81.3%"),
    ("SOL","market_analysis","mistral-7b-instruct-q3km",
     "Solana Market Analysis\n\nSOL/USD $127.40. Solana overtook Ethereum in DEX volume for 3rd week (Raydium + Jupiter). Coinbase futures listing adds institutional credibility.\n\nOn-Chain: DEX vol 7d $18.4B vs ETH $15.1B. Active addresses 2.3M/day. TPS avg 4,200 (peak 8,100). 1,200+ new meme token mints/day.\n\nSignal: STRONG BUY | Confidence: 93.1%"),
    ("XRP","regulatory_update","mistral-7b-instruct-q3km",
     "XRP Regulatory Intelligence\n\nRipple vs SEC: Final judgment issued — XRP NOT a security on public exchanges. Removes 4-year overhang.\n\nImpact: 14 US exchanges relisted XRP within 48h. BofA, JPMorgan, Deutsche Bank announced XRP settlement pilots. XRPL volume +340% in 72h.\n\nSignal: STRONG BUY | Confidence: 94.2%\nPrice target: $3.50 (6-month horizon)."),
    ("DOGE","social_sentiment","mistral-7b-instruct-q3km",
     "Dogecoin Social Sentiment\n\nDOGE social volume spiked 480% following Elon Musk tweet. X filing for payment licenses in all 50 states fuels DOGE integration speculation.\n\nMetrics: 847,000 mentions (24h, +480% vs 7d avg). Ratio: 73% bullish / 18% neutral / 9% bearish. 12 >1M follower influencers bullish.\n\nWhale: Top-50 wallet added 420M DOGE at $0.151.\n\nSignal: BUY | Confidence: 78.4%"),
]

def fg_label(v):
    if v >= 80: return "Extreme Greed"
    if v >= 60: return "Greed"
    if v >= 45: return "Neutral"
    if v >= 25: return "Fear"
    return "Extreme Fear"

def main():
    print("🌱  Seeding comprehensive demo data…\n")
    with engine.begin() as conn:

        # ── 1. price_data (14d × 15m candles) ────────────────────────────────
        print("  📈 price_data (14d × 5 coins)…")
        cnt = 0
        for coin, info in COINS.items():
            price = info["price"] * rng.uniform(0.82, 0.88)
            for i in range(14 * 24 * 4, 0, -1):
                price *= (1 + math.sin(i / 96) * 0.006 + rng.gauss(0, 0.003))
                price = max(price, info["price"] * 0.4)
                sp = price * 0.003
                o = round(price * rng.uniform(0.9985, 1.0015), 8)
                h = round(price + sp * rng.uniform(0.8, 1.6), 8)
                l = round(price - sp * rng.uniform(0.8, 1.6), 8)
                c = round(price * rng.uniform(0.999, 1.001), 8)
                v = round(info["vol"] * rng.uniform(0.4, 2.2) / (24 * 4), 4)
                t = (now - timedelta(minutes=i * 15)).strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn.execute(text(
                        "INSERT OR IGNORE INTO price_data (coin,interval,timestamp,open,high,low,close,volume) "
                        "VALUES (:c,'15m',:t,:o,:h,:l,:cl,:v)"
                    ), {"c": coin, "t": t, "o": o, "h": h, "l": l, "cl": c, "v": v})
                    cnt += 1
                except Exception:
                    pass
        print(f"     → {cnt} candles")

        # ── 2. technical_indicators (7d hourly, interval='1h') ────────────────
        print("  🔬 technical_indicators…")
        for coin, info in COINS.items():
            rsi = info["rsi"]
            price = info["price"]
            for h in range(168, 0, -1):
                rsi = max(22, min(82, rsi + rng.gauss(0, 3)))
                price *= (1 + rng.gauss(0, 0.004))
                bb_mid = price
                bb_std = price * 0.021
                macd = rng.gauss(0, price * 0.0008)
                sig = macd * rng.uniform(0.7, 1.3)
                try:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO technical_indicators
                          (coin,interval,timestamp,rsi,macd,macd_signal,macd_histogram,
                           bb_upper,bb_middle,bb_lower,atr)
                        VALUES (:c,'1h',:t,:rsi,:macd,:ms,:mh,:bu,:bm,:bl,:atr)
                    """), {
                        "c": coin, "t": ts(h),
                        "rsi": round(rsi, 2),
                        "macd": round(macd, 6), "ms": round(sig, 6), "mh": round(macd - sig, 6),
                        "bu": round(bb_mid + 2 * bb_std, 6), "bm": round(bb_mid, 6),
                        "bl": round(bb_mid - 2 * bb_std, 6),
                        "atr": round(price * 0.018, 6),
                    })
                except Exception:
                    pass
        print("     → 168h × 5 coins")

        # ── 3. sentiment_aggregated (7d hourly) ───────────────────────────────
        print("  💬 sentiment_aggregated…")
        for coin, info in COINS.items():
            sent = info["trend"] * rng.uniform(0.85, 1.0)
            for h in range(168, 0, -1):
                sent = max(0.06, min(0.96, sent + rng.gauss(0, 0.05)))
                n = rng.randint(6, 24)
                bull = int(n * max(0, sent - 0.05))
                bear = int(n * max(0, 0.9 - sent) * 0.6)
                neu = max(0, n - bull - bear)
                w = (now - timedelta(hours=h)).replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
                for ws in ("1h", "4h"):
                    try:
                        conn.execute(text("""
                            INSERT OR IGNORE INTO sentiment_aggregated
                              (coin,window_size,window_start,avg_sentiment,sample_count,
                               bullish_count,bearish_count,neutral_count,fud_count,
                               total_posts,sentiment_velocity,social_volume)
                            VALUES (:c,:ws,:w,:s,:n,:b,:br,:ne,:fud,:tp,:vel,:sv)
                        """), {
                            "c": coin, "ws": ws, "w": w,
                            "s": round(sent, 4), "n": n, "b": bull, "br": bear,
                            "ne": max(0, neu), "fud": max(0, n - bull - bear - neu),
                            "tp": n + rng.randint(0, 10),
                            "vel": round((sent - 0.5) * rng.uniform(0.05, 0.3), 4),
                            "sv": float(n + rng.randint(4, 25)),
                        })
                    except Exception:
                        pass
        print("     → 168h × 5 coins × 2 windows")

        # ── 4. signals ────────────────────────────────────────────────────────
        print("  📡 signals…")
        for i, (coin, stype, conf, price, reason) in enumerate(SIGNALS):
            try:
                conn.execute(text("""
                    INSERT INTO signals
                      (coin,signal_type,confidence,generated_at,price_at_signal,
                       sentiment_score,prediction_score,onchain_score,technical_score,
                       divergence_signal,reasoning)
                    VALUES (:c,:s,:conf,:t,:p,:sent,:pred,:onch,:tech,'NONE',:r)
                """), {
                    "c": coin, "s": stype, "conf": conf,
                    "t": ts(i * 3 + rng.randint(0, 2)),
                    "p": price, "sent": round(conf * rng.uniform(0.87, 1.0), 4),
                    "pred": round(conf * rng.uniform(0.80, 0.97), 4),
                    "onch": round(rng.uniform(0.45, 0.90), 4),
                    "tech": round(rng.uniform(0.42, 0.84), 4),
                    "r": reason,
                })
            except Exception as e:
                print(f"     signal err: {e}")
        print("     → 11 signals across 5 coins")

        # ── 5. news_articles ──────────────────────────────────────────────────
        print("  🗞️  news_articles…")
        for coin, lbl, score, title, url, src in ARTICLES:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO news_articles
                      (article_id,source,title,coin,published_at,url,sentiment_label,sentiment_score)
                    VALUES (:aid,:src,:t,:c,:pub,:url,:lbl,:s)
                """), {
                    "aid": uid(title), "src": src, "t": title, "c": coin,
                    "pub": ts(rng.randint(0, 20)), "url": url, "lbl": lbl, "s": score,
                })
            except Exception:
                pass
        print(f"     → {len(ARTICLES)} articles")

        # ── 6. sentiment_scores ───────────────────────────────────────────────
        print("  🧠 sentiment_scores…")
        for coin, lbl, score, title, url, src in ARTICLES:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO sentiment_scores
                      (source_type,source_id,coin,text_content,sentiment_label,
                       sentiment_score,confidence,model_used)
                    VALUES ('news',:sid,:c,:t,:lbl,:s,:conf,'mistral-7b-instruct-q3km')
                """), {
                    "sid": uid(title), "c": coin, "t": title[:500],
                    "lbl": lbl, "s": score, "conf": round(min(0.97, abs(score + rng.uniform(-0.04, 0.04))), 4),
                })
            except Exception:
                pass

        # ── 7. whale_transactions ─────────────────────────────────────────────
        print("  🐋 whale_transactions…")
        WHALES = [
            ("BTC","exchange_outflow","inflow",2400,87200,0),
            ("BTC","exchange_inflow","outflow",1100,86900,1),
            ("BTC","transfer","inflow",3800,85400,0),
            ("ETH","exchange_outflow","inflow",14200,2018,0),
            ("ETH","exchange_inflow","outflow",8500,2041,1),
            ("SOL","exchange_outflow","inflow",182000,124.5,0),
            ("SOL","exchange_inflow","outflow",95000,131.2,1),
            ("XRP","exchange_outflow","inflow",4800000,2.14,0),
            ("XRP","exchange_inflow","outflow",2100000,2.19,1),
            ("DOGE","transfer","inflow",420000000,0.158,0),
        ]
        for coin, ttype, direction, amt, price, is_ex_from in WHALES:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO whale_transactions
                      (coin,token_symbol,tx_hash,from_address,to_address,
                       value_usd,direction,tx_type,is_exchange_from,is_exchange_to,block_time)
                    VALUES (:c,:c,:h,:fa,:ta,:v,:d,:tt,:ief,:iet,:t)
                """), {
                    "c": coin, "h": uid(coin, ttype, amt),
                    "fa": f"0x{rng.randint(10**15,10**16-1):016x}",
                    "ta": f"0x{rng.randint(10**15,10**16-1):016x}",
                    "v": round(amt * price, 2), "d": direction, "tt": ttype,
                    "ief": is_ex_from, "iet": 1 - is_ex_from,
                    "t": ts(rng.randint(0, 24)),
                })
            except Exception:
                pass
        print("     → 10 whale transactions")

        # ── 8. onchain_metrics (7d, 4h window) ───────────────────────────────
        print("  ⛓️  onchain_metrics…")
        onchain_base = {
            "BTC":  {"in": 35e6,  "out": 52e6,  "wc": 18, "wv": 28e6,  "ws": 0.78},
            "ETH":  {"in": 42e6,  "out": 58e6,  "wc": 24, "wv": 35e6,  "ws": 0.67},
            "SOL":  {"in": 8e6,   "out": 14e6,  "wc": 31, "wv": 11e6,  "ws": 0.85},
            "XRP":  {"in": 15e6,  "out": 22e6,  "wc": 14, "wv": 18e6,  "ws": 0.91},
            "DOGE": {"in": 3.2e6, "out": 4.1e6, "wc": 9,  "wv": 3.8e6, "ws": 0.73},
        }
        for coin, base in onchain_base.items():
            for h in range(168, 0, -4):
                inflow  = base["in"]  * rng.uniform(0.7, 1.3)
                outflow = base["out"] * rng.uniform(0.7, 1.3)
                try:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO onchain_metrics
                          (coin,window_size,timestamp,exchange_inflow_usd,exchange_outflow_usd,
                           net_flow_usd,whale_tx_count,whale_volume_usd,whale_activity_score)
                        VALUES (:c,'4h',:t,:i,:o,:n,:wc,:wv,:ws)
                    """), {
                        "c": coin, "t": ts(h),
                        "i": round(inflow, 2), "o": round(outflow, 2),
                        "n": round(outflow - inflow, 2),
                        "wc": int(base["wc"] * rng.uniform(0.5, 1.8)),
                        "wv": round(base["wv"] * rng.uniform(0.6, 1.5), 2),
                        "ws": round(base["ws"] * rng.uniform(0.85, 1.0), 4),
                    })
                except Exception:
                    pass
        print("     → onchain_metrics 7d × 5 coins")

        # ── 9. fear_greed_index (30d) ─────────────────────────────────────────
        print("  😱 fear_greed_index…")
        fg = 52.0
        for d in range(30, -1, -1):
            fg = max(14, min(92, fg + rng.gauss(0, 7)))
            for h in [12, 0]:
                t = (now - timedelta(days=d, hours=h)).strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO fear_greed_index
                          (timestamp,index_value,label,sentiment_component,social_volume_component,
                           volume_momentum_component,volatility_component,whale_activity_component)
                        VALUES (:t,:v,:l,:sc,:svc,:vmc,:vc,:wac)
                    """), {
                        "t": t, "v": round(fg, 1), "l": fg_label(fg),
                        "sc": round(rng.uniform(0.42, 0.78), 3),
                        "svc": round(rng.uniform(0.38, 0.72), 3),
                        "vmc": round(rng.uniform(0.44, 0.68), 3),
                        "vc": round(rng.uniform(0.48, 0.74), 3),
                        "wac": round(rng.uniform(0.38, 0.82), 3),
                    })
                except Exception:
                    pass
        print("     → 30d fear & greed")

        # ── 10. narrative_tracking ────────────────────────────────────────────
        print("  🏷️  narrative_tracking…")
        NARR = {
            "BTC":  [("Bitcoin ETF",87),("Halving Cycle",74),("Institutional Adoption",61),("Macro Relief",45),("Store of Value",38)],
            "ETH":  [("Staking Yield",79),("Layer2 Scaling",68),("DeFi TVL",55),("Account Abstraction",42),("Gas Optimization",35)],
            "SOL":  [("DEX Volume Leader",92),("Meme Coins",71),("DePIN Growth",58),("Developer Grants",44),("NFT Renaissance",37)],
            "XRP":  [("Ripple Legal Win",95),("Banking Integration",78),("CBDC Pilot",62),("Mt Gox Distribution",49),("Cross-Border Payments",41)],
            "DOGE": [("Musk Effect",88),("X Payments",66),("Community Pump",52),("Whale Activity",45),("DogeLabs",31)],
        }
        for coin, narrs in NARR.items():
            for narr, base_mentions in narrs:
                for h in range(24):
                    for src in ("news","reddit"):
                        try:
                            conn.execute(text("""
                                INSERT OR IGNORE INTO narrative_tracking
                                  (coin,narrative,source_type,mention_count,timestamp)
                                VALUES (:c,:n,:s,:m,:t)
                            """), {
                                "c": coin, "n": narr, "s": src,
                                "m": max(1, int(base_mentions * rng.uniform(0.5, 1.5))),
                                "t": ts(h + rng.uniform(0, 0.9)),
                            })
                        except Exception:
                            pass
        print("     → narratives seeded")

        # ── 11. predictions ───────────────────────────────────────────────────
        print("  🤖 predictions…")
        MODELS = ["XGBoost_v3","LSTM_v2","AutoGluon_Ens"]
        for coin in COINS:
            for model in MODELS:
                for hz in [1, 4, 24]:
                    for i in range(18):
                        conf = rng.uniform(0.54, 0.92)
                        direction = rng.choices(["UP","DOWN","SIDEWAYS"],[0.45,0.35,0.20])[0]
                        hours_ago = i * hz + rng.randint(0, hz)
                        wc = None if hours_ago < hz else (1 if rng.random() < conf else 0)
                        try:
                            conn.execute(text("""
                                INSERT OR IGNORE INTO predictions
                                  (coin,model_name,horizon_hours,predicted_at,
                                   predicted_direction,confidence,was_correct,outcome_recorded_at)
                                VALUES (:c,:m,:h,:t,:d,:conf,:wc,:ot)
                            """), {
                                "c": coin, "m": model, "h": hz,
                                "t": ts(hours_ago), "d": direction,
                                "conf": round(conf, 4), "wc": wc,
                                "ot": ts(max(0, hours_ago - hz)) if wc is not None else None,
                            })
                        except Exception:
                            pass
        print("     → predictions seeded")

        # ── 12. model_accuracy ────────────────────────────────────────────────
        print("  🎯 model_accuracy…")
        MSTATS = {
            "XGBoost_v3":   {"acc":0.721,"prec":0.748,"rec":0.694,"f1":0.720,"sharpe":1.84},
            "LSTM_v2":      {"acc":0.688,"prec":0.712,"rec":0.661,"f1":0.685,"sharpe":1.52},
            "AutoGluon_Ens":{"acc":0.756,"prec":0.779,"rec":0.731,"f1":0.754,"sharpe":2.11},
            "Ensemble":     {"acc":0.768,"prec":0.791,"rec":0.744,"f1":0.767,"sharpe":2.28},
        }
        for coin in COINS:
            for mname, st in MSTATS.items():
                n = lambda: rng.uniform(-0.022, 0.022)
                try:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO model_accuracy
                          (coin,model_name,accuracy,precision,recall,f1_score,sharpe,horizon_h)
                        VALUES (:c,:m,:a,:p,:r,:f,:s,1)
                    """), {
                        "c": coin, "m": mname,
                        "a": round(st["acc"]+n(),4), "p": round(st["prec"]+n(),4),
                        "r": round(st["rec"]+n(),4), "f": round(st["f1"]+n(),4),
                        "s": round(st["sharpe"]+rng.uniform(-0.25,0.35),4),
                    })
                except Exception:
                    pass
        print("     → model_accuracy seeded")

        # ── 13. market_reports ────────────────────────────────────────────────
        print("  📋 market_reports…")
        for coin, rtype, model, body in REPORTS:
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO market_reports
                      (coin,report_type,report_text,model_used,generated_at)
                    VALUES (:c,:rt,:txt,:m,:t)
                """), {
                    "c": coin, "rt": rtype, "txt": body.strip(),
                    "m": model, "t": ts(rng.randint(0, 8)),
                })
            except Exception as e:
                print(f"     report err: {e}")
        print(f"     → {len(REPORTS)} market reports")

    print("\n✅  All done! Row counts:")
    import pandas as pd
    for tbl in ["price_data","technical_indicators","sentiment_aggregated","signals",
                "news_articles","whale_transactions","onchain_metrics","fear_greed_index",
                "narrative_tracking","predictions","model_accuracy","market_reports"]:
        try:
            cnt = pd.read_sql(f"SELECT COUNT(*) c FROM {tbl}", engine).iloc[0]["c"]
            print(f"   {tbl:32s} {cnt:>6} rows")
        except Exception as e:
            print(f"   {tbl:32s} ERROR: {e}")

if __name__ == "__main__":
    main()
