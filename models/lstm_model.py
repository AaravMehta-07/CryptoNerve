import numpy as np
import pandas as pd
import os
from loguru import logger
from config.settings import settings

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not available, LSTM model disabled")


class LSTMModel:
    def __init__(self, coin, horizon="4h", sequence_length=48):
        self.coin = coin
        self.horizon = horizon
        self.sequence_length = sequence_length
        self.model = None
        self.feature_columns = None
        self.scaler_params = None
        self.model_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"lstm_{coin}_{horizon}"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def _create_sequences(self, X, y):
        X_seq, y_seq = [], []
        for i in range(self.sequence_length, len(X)):
            X_seq.append(X[i - self.sequence_length:i])
            y_seq.append(y[i])
        return np.array(X_seq), np.array(y_seq)

    def _normalize(self, df, feature_columns):
        self.scaler_params = {}
        normalized = df.copy()
        for col in feature_columns:
            if col in normalized.columns:
                min_val = normalized[col].min()
                max_val = normalized[col].max()
                range_val = max_val - min_val if max_val != min_val else 1
                normalized[col] = (normalized[col] - min_val) / range_val
                self.scaler_params[col] = {"min": min_val, "max": max_val}
        return normalized

    def train(self, df, feature_columns, target_column):
        if not TF_AVAILABLE:
            logger.warning("TensorFlow not available, skipping LSTM training")
            return None

        normalized_df = self._normalize(df, feature_columns)
        available_cols = [c for c in feature_columns if c in normalized_df.columns]
        self.feature_columns = available_cols

        X = normalized_df[available_cols].values
        y = normalized_df[target_column].values

        X_seq, y_seq = self._create_sequences(X, y)
        split = int(len(X_seq) * 0.8)
        X_train, X_val = X_seq[:split], X_seq[split:]
        y_train, y_val = y_seq[:split], y_seq[split:]

        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(self.sequence_length, len(available_cols))),
            Dropout(0.2),
            LSTM(32, return_sequences=False),
            Dropout(0.2),
            Dense(16, activation="relu"),
            Dense(1, activation="sigmoid"),
        ])
        model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])

        early_stop = EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)
        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=50, batch_size=32,
            callbacks=[early_stop], verbose=0,
        )

        self.model = model
        model.save(self.model_path)

        val_acc = max(history.history.get("val_accuracy", [0]))
        logger.info(f"LSTM {self.coin} {self.horizon}: Val Acc = {val_acc:.4f}")

        return {"model": "lstm", "coin": self.coin, "horizon": self.horizon, "val_accuracy": round(val_acc, 4)}

    def predict(self, features_df):
        if not TF_AVAILABLE or self.model is None:
            self.load()
        if self.model is None:
            return None

        available_cols = [c for c in self.feature_columns if c in features_df.columns]
        normalized = self._normalize(features_df, available_cols)
        X = normalized[available_cols].values

        if len(X) < self.sequence_length:
            return None

        X_seq = X[-self.sequence_length:].reshape(1, self.sequence_length, len(available_cols))
        prob = float(self.model.predict(X_seq, verbose=0)[0][0])

        direction = "UP" if prob > 0.5 else "DOWN"
        confidence = abs(prob - 0.5) * 2

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
            logger.info(f"Loaded LSTM model for {self.coin}")
        except Exception as e:
            logger.warning(f"Could not load LSTM model: {e}")
