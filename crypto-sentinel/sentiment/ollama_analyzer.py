"""
Sentiment analyzer using Ollama HTTP API (localhost:11434).
Inference runs in the separate ollama.exe process.
"""
import json
import re
import os
import time
import urllib.request
from loguru import logger

# ── Ollama config ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M")

# Breathing room between requests to avoid overwhelming the GPU/CPU
LLM_INTER_CALL_SLEEP = 0.5  # seconds


class OllamaAnalyzer:
    """
    Sentiment analyzer backed by Ollama (Mistral 7B).
    Calls Ollama's REST API so inference happens in ollama.exe, not in Python.
    """

    def __init__(self):
        self.available = self._check_ollama()
        if self.available:
            logger.info(f"Ollama analyzer ready — model: {OLLAMA_MODEL}")
        else:
            logger.warning("Ollama not available — FinBERT fallback will be used")

    def _check_ollama(self) -> bool:
        """Ping Ollama and verify the model is loaded."""
        try:
            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/tags",
                headers={"User-Agent": "CryptoSentinel/2.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            models = [m.get("name", "") for m in data.get("models", [])]
            if any(OLLAMA_MODEL in m for m in models):
                return True
            logger.warning(f"Ollama running but '{OLLAMA_MODEL}' not found. Available: {models}")
            return False
        except Exception as e:
            logger.debug(f"Ollama not reachable: {e}")
            return False

    def _build_prompt(self, text: str, coin: str) -> str:
        return (
            f"[INST] You are a crypto market sentiment analyst specialising in {coin}.\n\n"
            f'Analyze the following text and return sentiment as JSON.\n'
            f'Do NOT default to 0.9 confidence — calibrate based on signal clarity.\n\n'
            f'TEXT: "{text[:900]}"\n\n'
            f"Output ONLY this JSON object, nothing else:\n"
            f'{{"label":"BULLISH|BEARISH|NEUTRAL|FUD",'
            f'"score":0.0_to_1.0,'
            f'"confidence":0.0_to_1.0,'
            f'"reasoning":"one sentence"}}\n\n'
            f"score: 0.0=very bearish, 0.5=neutral, 1.0=very bullish\n"
            f"confidence: how clear and unambiguous is the signal (varies per article)\n\n"
            f"Calibration examples:\n"
            f'>> "Bitcoin ETF gets SEC approval, record $4B inflows on day one"\n'
            f'   {{"label":"BULLISH","score":0.94,"confidence":0.91,"reasoning":"ETF approval unlocks institutional capital directly."}}\n'
            f'>> "Major exchange hacked, $200M drained, withdrawals suspended"\n'
            f'   {{"label":"FUD","score":0.07,"confidence":0.96,"reasoning":"Hack triggers immediate panic selling and loss of trust."}}\n'
            f'>> "Fed holds rates; crypto sees mixed signals with low volume"\n'
            f'   {{"label":"NEUTRAL","score":0.50,"confidence":0.55,"reasoning":"Mixed macro data gives no clear directional signal."}}\n'
            f'>> "Regulators debate new crypto bill, outcome highly uncertain"\n'
            f'   {{"label":"BEARISH","score":0.30,"confidence":0.63,"reasoning":"Regulatory uncertainty pressures prices, but unclear outcome."}}\n'
            f'>> "Bitcoin hashrate hits all-time high as miners expand capacity"\n'
            f'   {{"label":"BULLISH","score":0.65,"confidence":0.72,"reasoning":"Rising hashrate signals miner confidence in long-term value."}}\n\n'
            f"Now analyze the TEXT and output JSON only: [/INST]"
        )

    def analyze_sentiment(self, text: str, coin: str = "BTC"):
        if not self.available:
            return None

        prompt = self._build_prompt(text, coin)
        try:
            payload = json.dumps({
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 200,
                    "stop": ["[INST]", "\n\n"],
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{OLLAMA_BASE_URL}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "CryptoSentinel/2.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())

            result_text = resp.get("response", "").strip()

            json_match = re.search(r'\{[^{}]+\}', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    label = result.get("label", "NEUTRAL").upper().strip()
                    _LABEL_MAP = {
                        "POSITIVE": "BULLISH", "NEGATIVE": "BEARISH",
                        "FEAR": "FUD", "UNCERTAIN": "NEUTRAL",
                        "MIXED": "NEUTRAL", "CAUTIOUS": "NEUTRAL",
                        "BEARISH": "BEARISH", "BULLISH": "BULLISH",
                        "NEUTRAL": "NEUTRAL", "FUD": "FUD",
                    }
                    label = _LABEL_MAP.get(label, "NEUTRAL")
                    return {
                        "label": label,
                        "score": float(result.get("score", 0.5)),
                        "confidence": float(result.get("confidence", 0.5)),
                        "reasoning": result.get("reasoning", ""),
                        "model": f"ollama/{OLLAMA_MODEL}",
                    }
                except json.JSONDecodeError:
                    pass

            # Fallback: extract sentiment from prose
            rl = result_text.lower()
            if any(w in rl for w in ["bullish", "positive", "surge", "rally"]):
                lbl, sc = "BULLISH", 0.72
            elif any(w in rl for w in ["bearish", "negative", "crash", "dump", "fud"]):
                lbl, sc = "BEARISH", 0.28
            else:
                lbl, sc = "NEUTRAL", 0.50
            score_m = re.search(r'score[:\s]*([0-9]+\.?[0-9]*)', rl)
            if score_m:
                sc = max(0.0, min(1.0, float(score_m.group(1))))
            logger.info(f"Parsed from prose fallback: {lbl} score={sc}")
            return {
                "label": lbl, "score": sc, "confidence": 0.55,
                "reasoning": result_text[:120], "model": f"ollama/{OLLAMA_MODEL}",
            }
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Ollama inference error: {e}")

        return None

    def batch_analyze(self, texts_with_coins):
        results = []
        for i, item in enumerate(texts_with_coins):
            result = self.analyze_sentiment(item["text"], item.get("coin", "BTC"))
            if result:
                result["source_id"]    = item["source_id"]
                result["source_type"]  = item["source_type"]
                result["coin"]         = item["coin"]
                result["text_content"] = item["text"][:500]
                results.append(result)

            # Breathing room between inferences
            if i < len(texts_with_coins) - 1:
                time.sleep(LLM_INTER_CALL_SLEEP)

        return results
