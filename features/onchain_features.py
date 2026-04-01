"""On-chain feature utilities — called by FeatureEngineer."""
import pandas as pd
from database.connection import get_engine
from loguru import logger


def get_onchain_features(coin: str, window: str = "4h") -> pd.DataFrame:
    """Fetch on-chain metrics for a coin and time window."""
    engine = get_engine()
    query = f"""
    SELECT timestamp, whale_tx_count, whale_volume_usd,
           exchange_inflow_usd, exchange_outflow_usd, net_flow_usd,
           whale_activity_score
    FROM onchain_metrics
    WHERE coin = '{coin}' AND window_size = '{window}'
    ORDER BY timestamp ASC
    """
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        logger.error(f"On-chain features error: {e}")
        return pd.DataFrame()
