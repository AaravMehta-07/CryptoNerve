"""
AutoGluon Tabular model for crypto direction prediction.
Internally stacks LightGBM, XGBoost, CatBoost, RF, Extra Trees, NN.
"""
import os
import json
import numpy as np
from loguru import logger
from config.settings import settings

try:
    from autogluon.tabular import TabularPredictor
    AG_AVAILABLE = True
except ImportError:
    AG_AVAILABLE = False
    logger.warning("autogluon.tabular not installed — AutoGluon model disabled")


class AutoGluonModel:
    def __init__(self, coin, horizon="1h"):
        self.coin = coin
        self.horizon = horizon
        self.predictor = None
        self.model_dir = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"autogluon_{coin}_{horizon}"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def train(self, df, feature_columns, target_column, time_limit=600):
        """
        Train AutoGluon on the feature DataFrame.

        Args:
            df: DataFrame with features and target
            feature_columns: list of feature column names
            target_column: name of the binary target column (0/1)
            time_limit: seconds to spend training (default 600 = 10 min)
        """
        if not AG_AVAILABLE:
            logger.warning("AutoGluon not available, skipping training")
            return None

        available_cols = [c for c in feature_columns if c in df.columns]
        train_df = df[available_cols + [target_column]].copy()
        train_df = train_df.replace([np.inf, -np.inf], 0).fillna(0)

        # 80/20 time-ordered split
        split_idx = int(len(train_df) * 0.8)
        train_data = train_df.iloc[:split_idx]
        val_data = train_df.iloc[split_idx:]

        # Clear existing model directory to avoid "Learner is already fit" error
        import shutil
        if os.path.exists(self.model_dir):
            shutil.rmtree(self.model_dir)

        self.predictor = TabularPredictor(
            label=target_column,
            path=self.model_dir,
            eval_metric="accuracy",
            problem_type="binary",
            verbosity=1,
        )

        self.predictor.fit(
            train_data=train_data,
            tuning_data=val_data,
            time_limit=time_limit,
            presets="good_quality",
            use_bag_holdout=True,
            excluded_model_types=["KNN"],
        )

        # Evaluate
        val_preds = self.predictor.predict(val_data.drop(columns=[target_column]))
        val_acc = (val_preds == val_data[target_column]).mean()

        leaderboard = self.predictor.leaderboard(val_data, silent=True)
        best_model = leaderboard.iloc[0]["model"] if len(leaderboard) > 0 else "unknown"

        # Save metadata
        meta = {
            "coin": self.coin,
            "horizon": self.horizon,
            "features": available_cols,
            "val_accuracy": round(float(val_acc), 4),
            "best_internal_model": str(best_model),
            "n_models_trained": len(leaderboard),
        }
        with open(os.path.join(self.model_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(
            f"AutoGluon {self.coin} {self.horizon}: Val Acc = {val_acc:.4f}, "
            f"Best = {best_model}, Models = {len(leaderboard)}"
        )
        return meta

    def predict(self, features_df):
        """Get prediction from AutoGluon."""
        if self.predictor is None:
            self.load()
        if self.predictor is None:
            return None

        try:
            meta_path = os.path.join(self.model_dir, "meta.json")
            with open(meta_path) as f:
                meta = json.load(f)
            available_cols = [c for c in meta["features"] if c in features_df.columns]

            X = features_df[available_cols].copy()
            X = X.replace([np.inf, -np.inf], 0).fillna(0)

            # Get last row prediction with probabilities
            pred_proba = self.predictor.predict_proba(X)
            pred_class = self.predictor.predict(X)

            last_pred = int(pred_class.iloc[-1])
            direction = "UP" if last_pred == 1 else "DOWN"

            # Probabilities — AutoGluon returns DataFrame with columns 0, 1
            prob_up = float(pred_proba.iloc[-1][1]) if 1 in pred_proba.columns else 0.5
            prob_down = float(pred_proba.iloc[-1][0]) if 0 in pred_proba.columns else 0.5
            confidence = max(prob_up, prob_down)

            return {
                "direction": direction,
                "confidence": round(confidence, 4),
                "probabilities": {"UP": round(prob_up, 4), "DOWN": round(prob_down, 4)},
                "model": "autogluon",
            }
        except Exception as e:
            logger.error(f"AutoGluon predict error: {e}")
            return None

    def get_feature_importance(self):
        """Return AutoGluon's feature importance."""
        if self.predictor is None:
            return {}
        try:
            importance = self.predictor.feature_importance(num_shuffle_sets=3)
            return dict(zip(importance.index, importance["importance"]))
        except Exception:
            return {}

    def load(self):
        """Load a previously trained AutoGluon predictor."""
        if not AG_AVAILABLE:
            return
        try:
            self.predictor = TabularPredictor.load(self.model_dir)
            logger.info(f"Loaded AutoGluon model for {self.coin} {self.horizon}")
        except Exception as e:
            logger.warning(f"Could not load AutoGluon model: {e}")
