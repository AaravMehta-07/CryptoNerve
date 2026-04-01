from collections import Counter
from config.constants import CRYPTO_NARRATIVES
from loguru import logger


class NarrativeDetector:
    def __init__(self):
        self.narratives = CRYPTO_NARRATIVES

    def detect_narratives(self, texts):
        narrative_counts = Counter()
        for text in texts:
            if not text:
                continue
            text_lower = text.lower()
            for narrative in self.narratives:
                if narrative.lower() in text_lower:
                    narrative_counts[narrative] += 1
        return narrative_counts.most_common(10)

    def get_narrative_summary(self, texts):
        top_narratives = self.detect_narratives(texts)
        total_mentions = sum(count for _, count in top_narratives)

        summary = []
        for narrative, count in top_narratives:
            summary.append({
                "narrative": narrative,
                "mentions": count,
                "share_pct": round(count / max(total_mentions, 1) * 100, 1),
            })
        return summary
