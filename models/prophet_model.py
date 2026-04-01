from prophet import Prophet
import pandas as pd
import numpy as np
from loguru import logger
import pickle
import os
from config.settings import settings


class ProphetModel:
    def __init__(self, coin, horizon_hours=4):
        self.coin = coin
        self.horizon_hours = horizon_hours
        self.model = None
        self.model_path = os.path.join(
            settings.MODEL_ARTIFACTS_DIR, f"prophet_{coin}_{horizon_hours}h.pkl"
        )
        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)

    def train(self, price_df):
        df = price_df[["close"]].reset_index()
        df.columns = ["ds", "y"]
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)

        self.model = Prophet(
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=False,
        )
        self.model.fit(df)

        with open(self.model_path, "wb") as f:
            pickle.dump(self.model, f)

        logger.info(f"Prophet model trained for {self.coin} ({self.horizon_hours}h)")
        return {"model": "prophet", "coin": self.coin, "horizon": f"{self.horizon_hours}h"}

    def predict(self, current_price=None):
        if self.model is None:
            self.load()
        if self.model is None:
            return None

        periods = self.horizon_hours * 4  # 15-min intervals
        future = self.model.make_future_dataframe(periods=periods, freq="15min")
        forecast = self.model.predict(future)

        last_actual = forecast.iloc[-periods - 1]["yhat"]
        last_predicted = forecast.iloc[-1]["yhat"]
        predicted_change = (last_predicted - last_actual) / last_actual

        direction = (
            "UP" if predicted_change > 0.001
            else "DOWN" if predicted_change < -0.001
            else "SIDEWAYS"
        )

        last_row = forecast.iloc[-1]
        interval_width = last_row["yhat_upper"] - last_row["yhat_lower"]
        relative_width = interval_width / (last_row["yhat"] + 1e-8)
        confidence = max(0.3, min(0.9, 1 - relative_width))

        return {
            "direction": direction,
            "confidence": round(confidence, 4),
            "predicted_price": round(last_predicted, 2),
            "predicted_change_pct": round(predicted_change * 100, 4),
            "upper_bound": round(last_row["yhat_upper"], 2),
            "lower_bound": round(last_row["yhat_lower"], 2),
            "model": "prophet",
        }

    def load(self):
        try:
            with open(self.model_path, "rb") as f:
                self.model = pickle.load(f)
            logger.info(f"Loaded Prophet model for {self.coin}")
        except Exception as e:
            logger.warning(f"Could not load Prophet model: {e}")
