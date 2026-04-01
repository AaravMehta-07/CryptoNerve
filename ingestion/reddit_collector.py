"""
Reddit collection is disabled — replaced by premium crypto RSS feeds
(CoinDesk, CoinTelegraph, Crypto Briefing, The Block) in news_collector.py.

This stub class keeps existing imports from crashing.
"""
from loguru import logger


class RedditCollector:
    def __init__(self):
        logger.info("RedditCollector: disabled — using premium RSS feeds instead")

    def run(self):
        logger.info("RedditCollector.run() skipped — no-op stub")
        return 0
