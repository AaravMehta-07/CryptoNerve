"""
Local LLM analyzer using the bundled Mistral 7B GGUF via llama-cpp-python.
Drop-in replacement for the Ollama-based analyzer — same interface.
"""
import json
import re
import os
import time
import psutil
from loguru import logger
from config.settings import settings

# ── Hardware throttle constants ────────────────────────────────────────────
# Sleep between LLM calls so the CPU gets a breath between inferences
LLM_INTER_CALL_SLEEP = 1.0   # seconds
# Pause and wait if CPU is above this during a batch
LLM_CPU_PAUSE_THRESHOLD = 88  # %
LLM_CPU_PAUSE_SLEEP     = 3   # seconds to sleep when CPU is too hot
LLM_CPU_PAUSE_MAX_WAIT  = 30  # give up waiting after this many seconds

# Lazy-loaded singleton so the model is only loaded once per process
_llm_instance = None


def _get_llm():
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    try:
        from llama_cpp import Llama

        model_path = settings.LLM_MODEL_PATH
        if not os.path.exists(model_path):
            logger.error(f"GGUF not found: {model_path}")
            return None

        logger.info(f"Loading Mistral 7B GGUF from {model_path} …")
        _llm_instance = Llama(
            model_path=model_path,
            n_ctx=settings.LLM_N_CTX,
            n_gpu_layers=settings.LLM_N_GPU_LAYERS,
            n_threads=settings.LLM_N_THREADS,
            verbose=False,
        )
        logger.info("✅ Mistral 7B loaded successfully (local GGUF)")
        return _llm_instance

    except ImportError:
        logger.error("llama-cpp-python not installed. Run: pip install llama-cpp-python")
        return None
    except Exception as e:
        logger.error(f"Failed to load GGUF model: {e}")
        return None


class OllamaAnalyzer:
    """
    Sentiment analyzer backed by the local Mistral 7B GGUF.
    The class name is kept as OllamaAnalyzer for back-compat with
    existing imports in sentiment_engine.py.
    """

    def __init__(self):
        self.llm = _get_llm()
        self.available = self.llm is not None
        if self.available:
            logger.info(f"LocalLLM analyzer ready ({settings.LLM_MODEL_NAME})")
        else:
            logger.warning("LocalLLM not available — FinBERT fallback will be used")

    def _build_prompt(self, text: str, coin: str) -> str:
        # Key fix: no 'or' literals inside the JSON template — they anchor
        # Mistral to a fixed default confidence. Show 5 examples with
        # deliberately varied confidence so the model calibrates properly.
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
            output = self.llm(
                prompt,
                max_tokens=200,
                temperature=0.1,
                top_p=0.9,
                stop=["[INST]", "\n\n"],
                echo=False,
            )
            result_text = output["choices"][0]["text"].strip()

            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                label = result.get("label", "NEUTRAL").upper().strip()
                # Normalize synonyms Mistral sometimes outputs
                _LABEL_MAP = {
                    "POSITIVE":  "BULLISH",
                    "NEGATIVE":  "BEARISH",
                    "FEAR":      "FUD",
                    "UNCERTAIN": "NEUTRAL",
                    "MIXED":     "NEUTRAL",
                    "CAUTIOUS":  "NEUTRAL",
                    "BEARISH":   "BEARISH",
                    "BULLISH":   "BULLISH",
                    "NEUTRAL":   "NEUTRAL",
                    "FUD":       "FUD",
                }
                label = _LABEL_MAP.get(label, "NEUTRAL")
                return {
                    "label": label,
                    "score": float(result.get("score", 0.5)),
                    "confidence": float(result.get("confidence", 0.5)),
                    "reasoning": result.get("reasoning", ""),
                    "model": settings.LLM_MODEL_NAME,
                }

            logger.warning(f"Could not parse JSON from LLM: {result_text[:120]}")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
        except Exception as e:
            logger.error(f"Local LLM inference error: {e}")

        return None

    def batch_analyze(self, texts_with_coins):
        results = []
        for i, item in enumerate(texts_with_coins):
            # ── CPU gate: pause if system is running hot ───────────────────
            waited = 0
            while waited < LLM_CPU_PAUSE_MAX_WAIT:
                cpu = psutil.cpu_percent(interval=0.5)
                if cpu < LLM_CPU_PAUSE_THRESHOLD:
                    break
                logger.debug(
                    f"[throttle] LLM batch paused (item {i+1}/{len(texts_with_coins)}) "
                    f"— CPU {cpu:.0f}% > {LLM_CPU_PAUSE_THRESHOLD}%"
                )
                time.sleep(LLM_CPU_PAUSE_SLEEP)
                waited += LLM_CPU_PAUSE_SLEEP

            result = self.analyze_sentiment(item["text"], item.get("coin", "BTC"))
            if result:
                result["source_id"]   = item["source_id"]
                result["source_type"] = item["source_type"]
                result["coin"]        = item["coin"]
                result["text_content"] = item["text"][:500]
                results.append(result)

            # ── Breathing room between inferences ─────────────────────────
            if i < len(texts_with_coins) - 1:
                time.sleep(LLM_INTER_CALL_SLEEP)

        return results
