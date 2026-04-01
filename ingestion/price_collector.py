import requests
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from config.settings import settings
from config.coins import TRACKED_COINS
from database.connection import get_engine


class PriceCollector:
    def __init__(self):
        self.base_url = settings.BINANCE_BASE_URL
        self.engine = get_engine()

    def fetch_klines(self, symbol, interval="15m", limit=100):
        url = f"{self.base_url}/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            records = []
            for candle in data:
                records.append({
                    "timestamp": datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                    "quote_volume": float(candle[7]),
                    "num_trades": int(candle[8]),
                })
            return records
        except Exception as e:
            logger.error(f"Binance klines error for {symbol}: {e}")
            return []

    def fetch_current_price(self, symbol):
        url = f"{self.base_url}/api/v3/ticker/price"
        try:
            response = requests.get(url, params={"symbol": symbol}, timeout=5)
            data = response.json()
            return float(data["price"])
        except Exception as e:
            logger.error(f"Binance price error for {symbol}: {e}")
            return None

    def fetch_24h_stats(self, symbol):
        url = f"{self.base_url}/api/v3/ticker/24hr"
        try:
            response = requests.get(url, params={"symbol": symbol}, timeout=5)
            data = response.json()
            return {
                "price_change_pct": float(data["priceChangePercent"]),
                "volume_24h": float(data["volume"]),
                "quote_volume_24h": float(data["quoteVolume"]),
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "weighted_avg_price": float(data["weightedAvgPrice"]),
            }
        except Exception as e:
            logger.error(f"Binance 24h stats error for {symbol}: {e}")
            return None

    def fetch_wazirx_price(self, pair):
        try:
            url = "https://api.wazirx.com/sapi/v1/ticker/24hr"
            response = requests.get(url, params={"symbol": pair}, timeout=5)
            data = response.json()
            return {
                "inr_price": float(data["lastPrice"]),
                "inr_volume": float(data["volume"]),
            }
        except Exception as e:
            logger.error(f"WazirX error for {pair}: {e}")
            return None

    def fetch_historical_data(self, symbol, interval="15m", days=90):
        all_records = []
        end_time = int(datetime.now(timezone.utc).timestamp() * 1000)

        intervals_per_day = {"15m": 96, "1h": 24, "4h": 6, "1d": 1}
        candles_needed = days * intervals_per_day.get(interval, 96)
        requests_needed = (candles_needed // 1000) + 1

        for i in range(requests_needed):
            url = f"{self.base_url}/api/v3/klines"
            params = {"symbol": symbol, "interval": interval, "limit": 1000, "endTime": end_time}
            try:
                response = requests.get(url, params=params, timeout=10)
                data = response.json()

                if not data:
                    break

                for candle in data:
                    all_records.append({
                        "timestamp": datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": float(candle[5]),
                        "quote_volume": float(candle[7]),
                        "num_trades": int(candle[8]),
                    })

                end_time = data[0][0] - 1
                logger.info(f"Fetched batch {i + 1}/{requests_needed} for {symbol}")

            except Exception as e:
                logger.error(f"Historical fetch error: {e}")
                break

        return sorted(all_records, key=lambda x: x["timestamp"])

    def save_prices(self, coin_symbol, records, interval="15m"):
        if not records:
            return 0

        df = pd.DataFrame(records)
        df["coin"] = coin_symbol
        df["interval"] = interval

        saved = 0
        for _, row in df.iterrows():
            try:
                pd.DataFrame([row.to_dict()]).to_sql(
                    "price_data", self.engine, if_exists="append", index=False
                )
                saved += 1
            except Exception:
                pass

        logger.info(f"Saved {saved}/{len(records)} price records for {coin_symbol}")
        return saved

    def run(self):
        logger.info("Starting price collection cycle...")
        total = 0
        for symbol, info in TRACKED_COINS.items():
            records = self.fetch_klines(info["binance_symbol"], interval="15m", limit=10)
            total += self.save_prices(symbol, records, "15m")

        logger.info(f"Price cycle complete: {total} records saved")
        return total
