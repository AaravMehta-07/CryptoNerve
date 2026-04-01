"""
LLM report generator using the local Mistral 7B GGUF (llama-cpp-python).
Generates professional market intelligence reports via the self-hosted model.
"""
import json
from datetime import datetime, timezone
from loguru import logger
from config.settings import settings
from database.connection import get_engine
# Re-use the singleton LLM loader from the analyzer module
from sentiment.ollama_analyzer import _get_llm
import pandas as pd


class LLMReportGenerator:
    def __init__(self):
        self.llm = _get_llm()
        self.engine = get_engine()
        if self.llm:
            logger.info("LLMReportGenerator: using local Mistral 7B GGUF")
        else:
            logger.warning("LLMReportGenerator: LLM unavailable — reports will show error message")

    def _generate(self, prompt: str, max_tokens: int = 700) -> str:
        """Low-level generation wrapper with [INST] format."""
        if not self.llm:
            return "⚠️ Report generation unavailable — local Mistral 7B could not be loaded. Check logs."
        try:
            full_prompt = f"[INST] {prompt.strip()} [/INST]"
            output = self.llm(
                full_prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
                stop=["[INST]"],
                echo=False,
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return f"Report generation failed: {e}"

    def generate_coin_report(self, coin_data: dict) -> str:
        prompt = (
            f"You are an expert crypto market analyst writing a professional 4-paragraph intelligence report. "
            f"Use the data below, be specific with numbers, and end with a BUY/SELL/HOLD recommendation.\n\n"
            f"COIN: {coin_data.get('symbol','BTC')} ({coin_data.get('name','Bitcoin')})\n"
            f"Price: ${coin_data.get('price','N/A')}  |  24h Change: {coin_data.get('change_24h','N/A')}%\n"
            f"Sentiment Score: {coin_data.get('sentiment','N/A')} (0=bearish, 1=bullish)\n"
            f"Fear & Greed: {coin_data.get('fear_greed','N/A')}/100\n"
            f"RSI: {coin_data.get('rsi','N/A')}  |  MACD Signal: {coin_data.get('macd_signal','N/A')}\n"
            f"Whale Activity: {coin_data.get('whale_summary','N/A')}  |  Net Flow: {coin_data.get('net_flow','N/A')}\n"
            f"Ensemble Signal: {coin_data.get('signal','N/A')} ({coin_data.get('confidence','N/A')} confidence)\n"
            f"Top Narratives: {coin_data.get('top_narratives','N/A')}\n"
            f"Divergence: {coin_data.get('divergence','None detected')}\n\n"
            f"Write 4 paragraphs covering: (1) Current Market State, (2) Sentiment & Social Analysis, "
            f"(3) On-Chain Intelligence, (4) Actionable Outlook with BUY/SELL/HOLD.\n"
            f"DISCLAIMER: Educational purposes only. Not financial advice."
        )
        report = self._generate(prompt, max_tokens=800)
        self._save_report(coin_data.get("symbol"), "coin_analysis", report, coin_data)
        return report

    def generate_signal_explanation(self, signal_data: dict) -> str:
        prompt = (
            f"Explain this crypto trading signal in 2-3 clear sentences for a retail trader:\n\n"
            f"Signal: {signal_data.get('signal_type')} for {signal_data.get('coin')}\n"
            f"Confidence: {float(signal_data.get('confidence', 0)):.0%}\n"
            f"Reasoning: {signal_data.get('reasoning', 'N/A')}\n\n"
            f"Be specific and actionable. Mention the key factors."
        )
        return self._generate(prompt, max_tokens=250)

    def generate_market_overview(self) -> str:
        prompt = (
            "You are a crypto market analyst. Write a concise 3-paragraph market overview covering:\n"
            "1. Overall crypto market sentiment (fear vs greed, BTC dominance trends)\n"
            "2. Notable sector trends (DeFi, L2 scaling, AI tokens, memecoins)\n"
            "3. Key macro factors and events to watch this week\n\n"
            "Be data-driven and professional. DISCLAIMER: Educational only, not financial advice."
        )
        report = self._generate(prompt, max_tokens=600)
        self._save_report(None, "market_overview", report, {})
        return report

    def _save_report(self, coin, report_type, report_text, input_data):
        try:
            record = {
                "coin": coin,
                "report_type": report_type,
                "report_text": report_text,
                "model_used": settings.LLM_MODEL_NAME,
                "input_data_json": json.dumps(input_data, default=str),
                "generated_at": datetime.now(timezone.utc),
            }
            pd.DataFrame([record]).to_sql("market_reports", self.engine, if_exists="append", index=False)
        except Exception as e:
            logger.error(f"Report save error: {e}")
