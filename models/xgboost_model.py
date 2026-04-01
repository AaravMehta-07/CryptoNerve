"""
XGBoost GPU model with Optuna hyperparameter optimization for 1h crypto prediction.
"""
import xgboost as xgb
import numpy as np
import pandas as pd
import json
import os
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from loguru import logger
from config.settings import settings

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("Optuna not installed — using default hyperparameters")


class XGBoostModel:
    def __init__(self, coin, horizon="1h"):
        self.coin = coin
        self.horizon = horizon
        self.model = None
        self.feature_columns = None
        self.best_params = None
        self.model_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"xgboost_{coin}_{horizon}.json"
        )
        self.meta_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"xgboost_{coin}_{horizon}_meta.json"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def _optuna_objective(self, trial, X, y):
        """Optuna objective: maximize CV accuracy with TimeSeriesSplit."""
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 500),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10, log=True),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
            "gamma": trial.suggest_float("gamma", 0, 5),
        }

        tscv = TimeSeriesSplit(n_splits=5)
        scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = xgb.XGBClassifier(
                **params,
                tree_method="gpu_hist",
                eval_metric="logloss",
                use_label_encoder=False,
                random_state=42,
            )
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=20,
                verbose=False,
            )
            scores.append(accuracy_score(y_val, model.predict(X_val)))

        return np.mean(scores)

    def train(self, df, feature_columns, target_column, n_optuna_trials=30):
        """Train XGBoost with optional Optuna hyperparameter tuning."""
        self.feature_columns = feature_columns
        available_cols = [c for c in feature_columns if c in df.columns]
        X = df[available_cols].fillna(0).replace([np.inf, -np.inf], 0)
        y = df[target_column].astype(int)

        # Optuna hyperparameter optimization
        if OPTUNA_AVAILABLE and n_optuna_trials > 0:
            logger.info(f"XGBoost {self.coin}: Running {n_optuna_trials} Optuna trials...")
            study = optuna.create_study(direction="maximize")
            study.optimize(
                lambda trial: self._optuna_objective(trial, X, y),
                n_trials=n_optuna_trials,
                show_progress_bar=False,
            )
            self.best_params = study.best_params
            logger.info(f"XGBoost {self.coin}: Best Optuna accuracy = {study.best_value:.4f}")
        else:
            self.best_params = {
                "n_estimators": 200, "max_depth": 6, "learning_rate": 0.05,
                "subsample": 0.8, "colsample_bytree": 0.8,
            }

        # CV scores with best params
        tscv = TimeSeriesSplit(n_splits=5)
        scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train_cv, X_val_cv = X.iloc[train_idx], X.iloc[val_idx]
            y_train_cv, y_val_cv = y.iloc[train_idx], y.iloc[val_idx]

            model = xgb.XGBClassifier(
                **self.best_params,
                tree_method="gpu_hist",
                eval_metric="logloss",
                use_label_encoder=False,
                random_state=42,
            )
            model.fit(
                X_train_cv, y_train_cv,
                eval_set=[(X_val_cv, y_val_cv)],
                early_stopping_rounds=20,
                verbose=False,
            )
            scores.append(accuracy_score(y_val_cv, model.predict(X_val_cv)))

        # Final model on 80% train split
        split_idx = int(len(X) * 0.8)
        X_train_final, X_val_final = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train_final, y_val_final = y.iloc[:split_idx], y.iloc[split_idx:]

        self.model = xgb.XGBClassifier(
            **self.best_params,
            tree_method="gpu_hist",
            eval_metric="logloss",
            use_label_encoder=False,
            random_state=42,
        )
        self.model.fit(
            X_train_final, y_train_final,
            eval_set=[(X_val_final, y_val_final)],
            early_stopping_rounds=20,
            verbose=False,
        )

        # Save model + metadata
        self.model.save_model(self.model_path)
        meta = {
            "features": available_cols,
            "best_params": self.best_params,
            "cv_accuracy_mean": round(np.mean(scores), 4),
            "cv_accuracy_std": round(np.std(scores), 4),
            "val_accuracy": round(accuracy_score(y_val_final, self.model.predict(X_val_final)), 4),
        }
        with open(self.meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(
            f"XGBoost {self.coin} {self.horizon}: "
            f"CV Acc = {meta['cv_accuracy_mean']:.4f} ± {meta['cv_accuracy_std']:.4f}, "
            f"Val Acc = {meta['val_accuracy']:.4f}"
        )
        return {**meta, "model": "xgboost", "coin": self.coin, "horizon": self.horizon}

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
            self.model = xgb.XGBClassifier()
            self.model.load_model(self.model_path)
            with open(self.meta_path) as f:
                meta = json.load(f)
            self.feature_columns = meta["features"]
            self.best_params = meta.get("best_params", {})
            logger.info(f"Loaded XGBoost model for {self.coin} {self.horizon}")
        except Exception as e:
            logger.warning(f"Could not load XGBoost model: {e}")
