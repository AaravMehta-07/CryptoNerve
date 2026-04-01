import requests
from datetime import datetime, timezone
from loguru import logger
from config.settings import settings
from config.constants import WHALE_ALERT_THRESHOLD_USD
from database.connection import get_engine
from sqlalchemy import text
import pandas as pd


class OnchainCollector:
    def __init__(self):
        self.etherscan_key = settings.ETHERSCAN_API_KEY
        self.engine = get_engine()

        self.exchange_addresses = {
            "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
            "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
            "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
            "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
            "0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43": "Coinbase",
            "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
            "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
            "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
            "0x236f9f97e0e62388479bf9e5ba4889e46b0273c3": "WazirX",
        }

    def _is_exchange(self, address):
        return address.lower() in self.exchange_addresses

    def _get_exchange_name(self, address):
        return self.exchange_addresses.get(address.lower(), "Unknown")

    def fetch_eth_whale_transactions(self, min_value_eth=100):
        transactions = []
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "proxy",
                "action": "eth_blockNumber",
                "apikey": self.etherscan_key,
            }
            response = requests.get(url, params=params, timeout=10)
            latest_block = int(response.json()["result"], 16)

            # MED-06 FIX: fetch ETH price once, not per-transaction
            eth_price = self._get_eth_price()

            for address in list(self.exchange_addresses.keys())[:5]:
                params = {
                    "module": "account",
                    "action": "txlist",
                    "address": address,
                    "startblock": latest_block - 100,
                    "endblock": latest_block,
                    "page": 1,
                    "offset": 20,
                    "sort": "desc",
                    "apikey": self.etherscan_key,
                }
                try:
                    response = requests.get(url, params=params, timeout=10)
                    data = response.json()

                    if data["status"] == "1" and data["result"]:
                        for tx in data["result"]:
                            value_eth = int(tx["value"]) / 1e18
                            if value_eth >= min_value_eth:
                                value_usd = value_eth * eth_price

                                is_from_exchange = self._is_exchange(tx["from"])
                                is_to_exchange = self._is_exchange(tx["to"])

                                if is_from_exchange and not is_to_exchange:
                                    tx_type = "exchange_outflow"
                                elif not is_from_exchange and is_to_exchange:
                                    tx_type = "exchange_inflow"
                                else:
                                    tx_type = "transfer"

                                transactions.append({
                                    "tx_hash": tx["hash"],
                                    "blockchain": "ethereum",
                                    "from_address": tx["from"],
                                    "to_address": tx["to"],
                                    "value_usd": value_usd,
                                    "value_native": value_eth,
                                    "token_symbol": "ETH",
                                    "block_number": int(tx["blockNumber"]),
                                    "block_time": datetime.fromtimestamp(
                                        int(tx["timeStamp"]), tz=timezone.utc
                                    ).strftime('%Y-%m-%d %H:%M:%S'),
                                    "tx_type": tx_type,
                                    "is_exchange_from": is_from_exchange,
                                    "is_exchange_to": is_to_exchange,
                                })

                except Exception as e:
                    logger.error(f"Etherscan tx fetch error for {address[:10]}: {e}")

            logger.info(f"Fetched {len(transactions)} whale transactions")
        except Exception as e:
            logger.error(f"Etherscan block fetch error: {e}")

        return transactions

    def _get_eth_price(self):
        try:
            url = "https://api.binance.com/api/v3/ticker/price"
            response = requests.get(url, params={"symbol": "ETHUSDT"}, timeout=5)
            return float(response.json()["price"])
        except Exception:
            return 3000.0

    def aggregate_onchain_metrics(self, coin, window_hours=4):
        from database.sql_compat import time_ago
        cutoff = time_ago(hours=window_hours)
        query = text("""
        SELECT
            COUNT(*) as whale_tx_count,
            COALESCE(SUM(value_usd), 0) as whale_volume_usd,
            COALESCE(SUM(CASE WHEN tx_type = 'exchange_inflow' THEN value_usd ELSE 0 END), 0) as exchange_inflow_usd,
            COALESCE(SUM(CASE WHEN tx_type = 'exchange_outflow' THEN value_usd ELSE 0 END), 0) as exchange_outflow_usd,
            COUNT(CASE WHEN value_usd > :threshold THEN 1 END) as large_tx_count
        FROM whale_transactions
        WHERE token_symbol = :coin
        AND block_time > :cutoff
        """)
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    "coin": coin,
                    "threshold": WHALE_ALERT_THRESHOLD_USD,
                    "cutoff": cutoff,
                })
            if df.empty:
                return None

            row = df.iloc[0]
            # net_flow > 0 means outflow > inflow = coins leaving exchanges = accumulation
            net_flow = row["exchange_outflow_usd"] - row["exchange_inflow_usd"]
            max_expected_volume = 100_000_000
            whale_activity_score = min(row["whale_volume_usd"] / max_expected_volume, 1.0)

            return {
                "coin": coin,
                "window_size": f"{window_hours}h",
                "whale_tx_count": int(row["whale_tx_count"]),
                "whale_volume_usd": float(row["whale_volume_usd"]),
                "exchange_inflow_usd": float(row["exchange_inflow_usd"]),
                "exchange_outflow_usd": float(row["exchange_outflow_usd"]),
                "net_flow_usd": float(net_flow),
                "large_tx_count": int(row["large_tx_count"]),
                "whale_activity_score": float(whale_activity_score),
                # CRIT-05 FIX: column removed — not in schema; signal computed in signal_generator
            }
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            return None

    def save_transactions(self, transactions):
        """Batch insert whale transactions (MED-01)."""
        if not transactions:
            return 0

        insert_sql = text("""
            INSERT INTO whale_transactions
                (tx_hash, blockchain, from_address, to_address, value_usd, value_native,
                 token_symbol, block_number, block_time, tx_type, is_exchange_from, is_exchange_to)
            VALUES
                (:tx_hash, :blockchain, :from_address, :to_address, :value_usd, :value_native,
                 :token_symbol, :block_number, :block_time, :tx_type, :is_exchange_from, :is_exchange_to)
            ON CONFLICT (tx_hash) DO NOTHING
        """)
        saved = 0
        try:
            with self.engine.begin() as conn:
                for tx in transactions:
                    try:
                        conn.execute(insert_sql, tx)
                        saved += 1
                    except Exception as e:
                        logger.debug(f"TX insert skipped ({tx.get('tx_hash', '')[:10]}): {e}")
        except Exception as e:
            logger.error(f"Batch whale_transactions insert error: {e}")

        logger.info(f"Saved {saved}/{len(transactions)} whale transactions")
        return saved

    def run(self):
        logger.info("Starting on-chain collection cycle...")
        txs = self.fetch_eth_whale_transactions(min_value_eth=50)
        self.save_transactions(txs)

        insert_sql = text("""
            INSERT INTO onchain_metrics
                (coin, timestamp, window_size, whale_tx_count, whale_volume_usd,
                 exchange_inflow_usd, exchange_outflow_usd, net_flow_usd,
                 large_tx_count, whale_activity_score)
            VALUES
                (:coin, :timestamp, :window_size, :whale_tx_count, :whale_volume_usd,
                 :exchange_inflow_usd, :exchange_outflow_usd, :net_flow_usd,
                 :large_tx_count, :whale_activity_score)
            ON CONFLICT (coin, timestamp, window_size) DO NOTHING
        """)
        try:
            with self.engine.begin() as conn:
                for coin in ["ETH", "BTC"]:
                    for window in [1, 4, 24]:
                        metrics = self.aggregate_onchain_metrics(coin, window)
                        if metrics:
                            metrics["timestamp"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                            try:
                                conn.execute(insert_sql, metrics)
                            except Exception as e:
                                logger.debug(f"Onchain metrics insert skipped: {e}")
        except Exception as e:
            logger.error(f"Onchain metrics batch insert error: {e}")

        logger.info(f"On-chain cycle complete: {len(txs)} transactions")
        return len(txs)
