TRACKED_COINS = {
    "BTC": {
        "symbol": "BTCUSDT",
        "name": "Bitcoin",
        "binance_symbol": "BTCUSDT",
        "coingecko_id": "bitcoin",
        "subreddits": ["bitcoin", "cryptocurrency"],
        "etherscan_contract": None,
        "news_keywords": ["bitcoin", "BTC", "btc"],
        "color": "#F7931A",
    },
    "ETH": {
        "symbol": "ETHUSDT",
        "name": "Ethereum",
        "binance_symbol": "ETHUSDT",
        "coingecko_id": "ethereum",
        "subreddits": ["ethereum", "ethtrader", "cryptocurrency"],
        "etherscan_contract": None,
        "news_keywords": ["ethereum", "ETH", "ether"],
        "color": "#627EEA",
    },
    "SOL": {
        "symbol": "SOLUSDT",
        "name": "Solana",
        "binance_symbol": "SOLUSDT",
        "coingecko_id": "solana",
        "subreddits": ["solana", "cryptocurrency"],
        "etherscan_contract": None,
        "news_keywords": ["solana", "SOL"],
        "color": "#00FFA3",
    },
    "BNB": {
        "symbol": "BNBUSDT",
        "name": "BNB",
        "binance_symbol": "BNBUSDT",
        "coingecko_id": "binancecoin",
        "subreddits": ["binance", "cryptocurrency"],
        "etherscan_contract": None,
        "news_keywords": ["BNB", "binance coin"],
        "color": "#F3BA2F",
    },
    "XRP": {
        "symbol": "XRPUSDT",
        "name": "XRP",
        "binance_symbol": "XRPUSDT",
        "coingecko_id": "ripple",
        "subreddits": ["ripple", "xrp", "cryptocurrency"],
        "etherscan_contract": None,
        "news_keywords": ["XRP", "ripple"],
        "color": "#00AAE4",
    },
}

# India-specific exchange price tracking
INDIA_EXCHANGES = {
    "wazirx": {
        "base_url": "https://api.wazirx.com/sapi/v1",
        "pairs": {
            "BTC": "btcinr",
            "ETH": "ethinr",
            "SOL": "solinr",
        },
    }
}
