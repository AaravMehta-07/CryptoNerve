import xgboost as xgb
import numpy as np
import pandas as pd
import pickle
import os
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from loguru import logger
from config.settings import settings


class XGBoostModel:
    def __init__(self, coin, horizon="1h"):
        self.coin = coin
        self.horizon = horizon
        self.model = None
        self.feature_columns = None
        self.model_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"xgboost_{coin}_{horizon}.pkl"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def train(self, df, feature_columns, target_column):
        self.feature_columns = feature_columns
        available_cols = [c for c in feature_columns if c in df.columns]
        X = df[available_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = df[target_column].astype(int)

        tscv = TimeSeriesSplit(n_splits=5)
        scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, random_state=42,
                eval_metric="logloss", use_label_encoder=False,
                early_stopping_rounds=20,
            )
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            scores.append(accuracy_score(y_val, model.predict(X_val)))

        # Final model on all data
        self.model = xgb.XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, random_state=42,
            eval_metric="logloss", use_label_encoder=False,
        )
        self.model.fit(X, y, verbose=False)

        with open(self.model_path, "wb") as f:
            pickle.dump({"model": self.model, "features": available_cols}, f)

        metrics = {
            "model": "xgboost",
            "coin": self.coin,
            "horizon": self.horizon,
            "cv_accuracy_mean": round(np.mean(scores), 4),
            "cv_accuracy_std": round(np.std(scores), 4),
        }
        logger.info(f"XGBoost {self.coin} {self.horizon}: CV Acc = {metrics['cv_accuracy_mean']:.4f}")
        return metrics

    def predict(self, features_df):
        if self.model is None:
            self.load()
        if self.model is None:
            return None

        available_cols = [c for c in self.feature_columns if c in features_df.columns]
        X = features_df[available_cols].fillna(0).replace([np.inf, -np.inf], 0)

        proba = self.model.predict_proba(X)
        pred_class = self.model.predict(X)

        direction = "UP" if pred_class[-1] == 1 else "DOWN"
        confidence = float(max(proba[-1]))

        return {
            "direction": direction,
            "confidence": confidence,
            "probabilities": {"UP": float(proba[-1][1]), "DOWN": float(proba[-1][0])},
            "model": "xgboost",
        }

    def get_feature_importance(self):
        if self.model is None:
            return {}
        return dict(zip(self.feature_columns, self.model.feature_importances_))

    def load(self):
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.feature_columns = data["features"]
            logger.info(f"Loaded XGBoost model for {self.coin} {self.horizon}")
        except Exception as e:
            logger.warning(f"Could not load XGBoost model: {e}")
