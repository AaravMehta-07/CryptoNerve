# Sentiment Labels
BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"
FUD = "FUD"

SENTIMENT_LABELS = [BULLISH, NEUTRAL, BEARISH, FUD]

# Signal Types
BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"
STRONG_BUY = "STRONG_BUY"
STRONG_SELL = "STRONG_SELL"

# Fear & Greed Zones
FEAR_GREED_ZONES = {
    (0, 25): "Extreme Fear",
    (25, 45): "Fear",
    (45, 55): "Neutral",
    (55, 75): "Greed",
    (75, 100): "Extreme Greed",
}

# Crypto Narratives for Detection
CRYPTO_NARRATIVES = [
    "ETF", "regulation", "halving", "adoption", "hack", "SEC",
    "whale", "DeFi", "staking", "inflation", "Fed", "recession",
    "India ban", "RBI", "institutional", "CBDC", "mining",
    "layer 2", "airdrop", "liquidation", "short squeeze",
    "bitcoin dominance", "altseason", "memecoin", "AI crypto",
    "Binance", "Coinbase", "WazirX", "CoinDCX",
    "30% tax", "1% TDS", "crypto tax India",
    "bull run", "bear market", "accumulation", "distribution",
    "blackrock", "grayscale", "microstrategy",
]

# Technical Indicator Windows
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
ATR_PERIOD = 14
OBV_PERIOD = 20

# Model Thresholds
BUY_SENTIMENT_THRESHOLD = 0.65
SELL_SENTIMENT_THRESHOLD = 0.35
MIN_SIGNAL_CONFIDENCE = 0.55
WHALE_ALERT_THRESHOLD_USD = 1_000_000

# Backtesting
INITIAL_CAPITAL = 10_000
POSITION_SIZE_PCT = 0.10  # 10% of capital per trade
MAX_OPEN_POSITIONS = 3
