from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch
from loguru import logger


class FinBERTAnalyzer:
    def __init__(self):
        self.model_name = "ProsusAI/finbert"
        self.tokenizer = None
        self.model = None
        self.pipe = None
        self._load_model()

    def _load_model(self):
        try:
            logger.info("Loading FinBERT model...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.pipe = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1,
                max_length=512,
                truncation=True,
            )
            logger.info("FinBERT loaded successfully")
            self.available = True
        except Exception as e:
            logger.error(f"FinBERT load error: {e}")
            self.available = False

    def analyze_sentiment(self, text, coin="BTC"):
        if not self.available:
            return None

        try:
            result = self.pipe(text[:512])[0]
            label_map = {
                "positive": ("BULLISH", lambda s: 0.5 + s * 0.5),
                "negative": ("BEARISH", lambda s: 0.5 - s * 0.5),
                "neutral": ("NEUTRAL", lambda s: 0.5),
            }

            finbert_label = result["label"].lower()
            crypto_label, score_fn = label_map.get(finbert_label, ("NEUTRAL", lambda s: 0.5))
            score = score_fn(result["score"])

            return {
                "label": crypto_label,
                "score": round(score, 4),
                "confidence": round(result["score"], 4),
                "reasoning": f"FinBERT classified as {finbert_label} with {result['score']:.2%} confidence",
                "model": "finbert",
            }
        except Exception as e:
            logger.error(f"FinBERT analysis error: {e}")
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
