"""
LSTM model with Optuna hyperparameter tuning for 1h crypto prediction.
- Sequence length: 24 timesteps (24h lookback on 1h candles)
- Architecture tuned per coin via Optuna
- Scaler params persisted separately to prevent leakage at inference
"""
import numpy as np
import pandas as pd
import os
import json
from loguru import logger
from config.settings import settings

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.optimizers import Adam
    TF_AVAILABLE = True
    # Limit GPU memory growth so XGBoost + LSTM can share the 4GB GTX 1650
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        tf.config.experimental.set_memory_growth(gpus[0], True)
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available — LSTM model disabled")


class LSTMModel:
    def __init__(self, coin, horizon="1h", sequence_length=24):
        self.coin = coin
        self.horizon = horizon
        self.sequence_length = sequence_length  # 24h lookback
        self.model = None
        self.feature_columns = None
        self.scaler_params = None
        self.best_params = None
        self.model_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"lstm_{coin}_{horizon}"
        )
        self.scaler_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"lstm_{coin}_{horizon}_scaler.json"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def _create_sequences(self, X, y):
        X_seq, y_seq = [], []
        for i in range(self.sequence_length, len(X)):
            X_seq.append(X[i - self.sequence_length:i])
            y_seq.append(y[i])
        return np.array(X_seq), np.array(y_seq)

    def _normalize(self, df, feature_columns):
        """Fit scaler on training data and persist params."""
        self.scaler_params = {}
        normalized = df.copy()
        for col in feature_columns:
            if col in normalized.columns:
                min_val = float(normalized[col].min())
                max_val = float(normalized[col].max())
                range_val = max_val - min_val if max_val != min_val else 1.0
                normalized[col] = (normalized[col] - min_val) / range_val
                self.scaler_params[col] = {"min": min_val, "max": max_val}
        return normalized

    def _apply_normalize(self, df, feature_columns):
        """Apply training-time scaler params — no re-fitting (prevents leakage)."""
        if not self.scaler_params:
            logger.warning("LSTM: scaler_params missing — predictions may be inaccurate")
            return df
        normalized = df.copy()
        for col in feature_columns:
            if col in normalized.columns and col in self.scaler_params:
                p = self.scaler_params[col]
                range_val = p["max"] - p["min"] if p["max"] != p["min"] else 1.0
                normalized[col] = (normalized[col] - p["min"]) / range_val
        return normalized

    def _build_model(self, n_features, units1=64, units2=32, dropout=0.2, lr=0.001):
        """Build LSTM architecture — parameters tunable via Optuna."""
        model = Sequential([
            LSTM(units1, return_sequences=True,
                 input_shape=(self.sequence_length, n_features)),
            BatchNormalization(),
            Dropout(dropout),
            LSTM(units2, return_sequences=False),
            Dropout(dropout),
            Dense(16, activation="relu"),
            Dense(1, activation="sigmoid"),
        ])
        model.compile(
            optimizer=Adam(learning_rate=lr),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        return model

    def _optuna_objective(self, trial, X_seq, y_seq):
        """Optuna objective for LSTM architecture search."""
        units1 = trial.suggest_categorical("units1", [32, 64, 128])
        units2 = trial.suggest_categorical("units2", [16, 32, 64])
        dropout = trial.suggest_float("dropout", 0.1, 0.4)
        lr = trial.suggest_float("lr", 1e-4, 1e-2, log=True)

        split = int(len(X_seq) * 0.8)
        X_train, X_val = X_seq[:split], X_seq[split:]
        y_train, y_val = y_seq[:split], y_seq[split:]

        model = self._build_model(X_seq.shape[2], units1, units2, dropout, lr)
        early_stop = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)

        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=30, batch_size=32,
            callbacks=[early_stop], verbose=0,
        )
        val_acc = max(history.history.get("val_accuracy", [0]))
        tf.keras.backend.clear_session()
        return val_acc

    def train(self, df, feature_columns, target_column, n_optuna_trials=15):
        if not TF_AVAILABLE:
            logger.warning("TensorFlow not available, skipping LSTM training")
            return None

        available_cols = [c for c in feature_columns if c in df.columns]
        self.feature_columns = available_cols

        normalized_df = self._normalize(df, available_cols)
        X = normalized_df[available_cols].values
        y = df[target_column].values

        X_seq, y_seq = self._create_sequences(X, y)
        if len(X_seq) < 50:
            logger.warning(f"LSTM {self.coin}: insufficient sequences ({len(X_seq)})")
            return None

        # Optuna architecture search
        if OPTUNA_AVAILABLE and n_optuna_trials > 0:
            logger.info(f"LSTM {self.coin}: Running {n_optuna_trials} Optuna trials...")
            study = optuna.create_study(direction="maximize")
            study.optimize(
                lambda trial: self._optuna_objective(trial, X_seq, y_seq),
                n_trials=n_optuna_trials,
                show_progress_bar=False,
            )
            self.best_params = study.best_params
            logger.info(f"LSTM {self.coin}: Best Optuna val_acc = {study.best_value:.4f}, params = {self.best_params}")
        else:
            self.best_params = {"units1": 64, "units2": 32, "dropout": 0.2, "lr": 0.001}

        # Final training with best params
        split = int(len(X_seq) * 0.8)
        X_train, X_val = X_seq[:split], X_seq[split:]
        y_train, y_val = y_seq[:split], y_seq[split:]

        self.model = self._build_model(
            X_seq.shape[2],
            self.best_params.get("units1", 64),
            self.best_params.get("units2", 32),
            self.best_params.get("dropout", 0.2),
            self.best_params.get("lr", 0.001),
        )

        callbacks = [
            EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True),
            ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=4, min_lr=1e-6),
        ]
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=60, batch_size=32,
            callbacks=callbacks, verbose=0,
        )

        val_acc = max(history.history.get("val_accuracy", [0]))
        self.model.save(self.model_path)

        # Persist scaler + metadata
        with open(self.scaler_path, "w") as f:
            json.dump({
                "scaler_params": self.scaler_params,
                "features": available_cols,
                "best_params": self.best_params,
                "val_accuracy": round(float(val_acc), 4),
            }, f, indent=2)

        logger.info(f"LSTM {self.coin} {self.horizon}: Val Acc = {val_acc:.4f}")
        return {
            "model": "lstm", "coin": self.coin, "horizon": self.horizon,
            "val_accuracy": round(float(val_acc), 4),
            "best_params": self.best_params,
        }

    def predict(self, features_df):
        if not TF_AVAILABLE:
            return None
        if self.model is None:
            self.load()
        if self.model is None:
            return None

        available_cols = [c for c in self.feature_columns if c in features_df.columns]
        normalized = self._apply_normalize(features_df, available_cols)
        X = normalized[available_cols].values

        if len(X) < self.sequence_length:
            logger.warning(f"LSTM {self.coin}: insufficient rows ({len(X)} < {self.sequence_length})")
            return None

        X_seq = X[-self.sequence_length:].reshape(1, self.sequence_length, len(available_cols))
        prob = float(self.model.predict(X_seq, verbose=0)[0][0])

        direction = "UP" if prob > 0.5 else "DOWN"
        confidence = abs(prob - 0.5) * 2  # rescale to 0-1

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "probabilities": {"UP": round(prob, 4), "DOWN": round(1 - prob, 4)},
            "model": "lstm",
        }

    def load(self):
        if not TF_AVAILABLE:
            return
        try:
            self.model = load_model(self.model_path)
            with open(self.scaler_path) as f:
                meta = json.load(f)
            self.scaler_params = meta["scaler_params"]
            self.feature_columns = meta["features"]
            self.best_params = meta.get("best_params", {})
            logger.info(f"Loaded LSTM model for {self.coin} {self.horizon}")
        except Exception as e:
            logger.warning(f"Could not load LSTM model: {e}")
