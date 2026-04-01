import shap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
import base64
from loguru import logger
from models.xgboost_model import XGBoostModel
from features.feature_engineer import FeatureEngineer


class SHAPExplainer:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()

    def explain_prediction(self, coin, horizon="4h"):
        try:
            xgb_model = XGBoostModel(coin, horizon)
            xgb_model.load()

            if xgb_model.model is None:
                return None

            df = self.feature_engineer.build_training_features(coin, days=7)
            if df is None:
                return None

            available_cols = [c for c in xgb_model.feature_columns if c in df.columns]
            X = df[available_cols].fillna(0).replace([np.inf, -np.inf], 0)

            explainer = shap.TreeExplainer(xgb_model.model)
            shap_values = explainer.shap_values(X.tail(1))

            feature_impact = dict(zip(available_cols, shap_values[0]))
            sorted_impact = sorted(feature_impact.items(), key=lambda x: abs(x[1]), reverse=True)

            # Waterfall plot
            shap.waterfall_plot(
                shap.Explanation(
                    values=shap_values[0],
                    base_values=explainer.expected_value,
                    data=X.tail(1).values[0],
                    feature_names=available_cols,
                ),
                max_display=15, show=False,
            )
            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close()
            buf.seek(0)
            waterfall_b64 = base64.b64encode(buf.getvalue()).decode()

            # Summary plot
            shap.summary_plot(
                explainer.shap_values(X.tail(50)), X.tail(50),
                feature_names=available_cols, show=False, max_display=15,
            )
            plt.tight_layout()
            buf2 = io.BytesIO()
            plt.savefig(buf2, format="png", dpi=100, bbox_inches="tight")
            plt.close()
            buf2.seek(0)
            summary_b64 = base64.b64encode(buf2.getvalue()).decode()

            return {
                "coin": coin, "horizon": horizon,
                "top_features": sorted_impact[:10],
                "waterfall_plot_b64": waterfall_b64,
                "summary_plot_b64": summary_b64,
                "base_value": float(explainer.expected_value),
                "prediction_value": float(shap_values[0].sum() + explainer.expected_value),
                "explanation_text": self._generate_text_explanation(sorted_impact[:5], coin),
            }
        except Exception as e:
            logger.error(f"SHAP explanation error: {e}")
            return None

    def _generate_text_explanation(self, top_features, coin):
        parts = [f"{coin} prediction explanation:"]
        for feature, impact in top_features:
            direction = "↑ bullish" if impact > 0 else "↓ bearish"
            parts.append(f"  • {feature}: {direction} impact ({impact:+.4f})")
        return "\n".join(parts)
