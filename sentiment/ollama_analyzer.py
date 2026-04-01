"""
Local LLM analyzer using the bundled Mistral 7B GGUF via llama-cpp-python.
Drop-in replacement for the Ollama-based analyzer — same interface.
"""
import json
import re
import os
from loguru import logger
from config.settings import settings

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
        # Mistral-Instruct chat format: [INST] … [/INST]
        return (
            f"[INST] You are a crypto market sentiment analyst. "
            f"Analyze the following text about {coin} and classify the sentiment.\n\n"
            f'TEXT: "{text[:900]}"\n\n'
            f"Respond in EXACTLY this JSON format, nothing else:\n"
            f'{{"label": "BULLISH" or "BEARISH" or "NEUTRAL" or "FUD", '
            f'"score": <float 0.0-1.0 where 0=extremely bearish, 0.5=neutral, 1.0=extremely bullish>, '
            f'"confidence": <float 0.0-1.0>, '
            f'"reasoning": "<one sentence>"}}\n\n'
            f"Examples:\n"
            f'- "Bitcoin ETF approved!" → {{"label":"BULLISH","score":0.92,"confidence":0.95,"reasoning":"ETF approval is a major bullish catalyst"}}\n'
            f'- "SEC sues exchange" → {{"label":"BEARISH","score":0.15,"confidence":0.88,"reasoning":"Regulatory action creates selling pressure"}}\n\n'
            f"Respond with JSON only: [/INST]"
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
                label = result.get("label", "NEUTRAL").upper()
                if label not in ("BULLISH", "BEARISH", "NEUTRAL", "FUD"):
                    label = "NEUTRAL"
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
        for item in texts_with_coins:
            result = self.analyze_sentiment(item["text"], item.get("coin", "BTC"))
            if result:
                result["source_id"] = item["source_id"]
                result["source_type"] = item["source_type"]
                result["coin"] = item["coin"]
                result["text_content"] = item["text"][:500]
                results.append(result)
        return results
