import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger
from database.connection import get_engine
from sqlalchemy import text


class AccuracyTracker:
    def __init__(self):
        self.engine = get_engine()

    def update_prediction_outcomes(self):
        query = """
        SELECT p.id, p.coin, p.predicted_at, p.horizon_hours, p.predicted_direction
        FROM predictions p
        WHERE p.actual_direction IS NULL
        AND p.predicted_at < NOW() - (p.horizon_hours || ' hours')::INTERVAL
        LIMIT 100
        """
        try:
            predictions = pd.read_sql(query, self.engine)
            if predictions.empty:
                return 0

            updated = 0
            for _, pred in predictions.iterrows():
                target_time = pred["predicted_at"] + timedelta(hours=int(pred["horizon_hours"]))

                price_query = f"""
                SELECT
                    (SELECT close FROM price_data
                     WHERE coin = '{pred["coin"]}' AND timestamp <= '{pred["predicted_at"]}'
                     ORDER BY timestamp DESC LIMIT 1) as price_at_prediction,
                    (SELECT close FROM price_data
                     WHERE coin = '{pred["coin"]}' AND timestamp <= '{target_time}'
                     ORDER BY timestamp DESC LIMIT 1) as price_at_target
                """
                prices = pd.read_sql(price_query, self.engine)
                if prices.empty or prices.iloc[0]["price_at_prediction"] is None:
                    continue

                price_at_pred = prices.iloc[0]["price_at_prediction"]
                price_at_target = prices.iloc[0]["price_at_target"]
                if price_at_target is None:
                    continue

                actual_change = (price_at_target - price_at_pred) / price_at_pred
                actual_direction = (
                    "UP" if actual_change > 0.001
                    else "DOWN" if actual_change < -0.001
                    else "SIDEWAYS"
                )
                was_correct = actual_direction == pred["predicted_direction"]

                with self.engine.connect() as conn:
                    conn.execute(text(f"""
                        UPDATE predictions
                        SET actual_direction = '{actual_direction}',
                            actual_price_change_pct = {actual_change * 100},
                            was_correct = {was_correct},
                            outcome_recorded_at = NOW()
                        WHERE id = {pred["id"]}
                    """))
                    conn.commit()
                updated += 1

            logger.info(f"Updated {updated} prediction outcomes")
            return updated
        except Exception as e:
            logger.error(f"Accuracy tracking error: {e}")
            return 0

    def get_model_accuracy(self, model_name=None, coin=None, horizon_hours=None):
        conditions = ["was_correct IS NOT NULL"]
        if model_name:
            conditions.append(f"model_name = '{model_name}'")
        if coin:
            conditions.append(f"coin = '{coin}'")
        if horizon_hours:
            conditions.append(f"horizon_hours = {horizon_hours}")

        query = f"""
        SELECT
            model_name, coin, horizon_hours,
            COUNT(*) as total_predictions,
            SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct_predictions,
            ROUND(AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) as accuracy,
            ROUND(AVG(confidence)::numeric, 4) as avg_confidence
        FROM predictions
        WHERE {" AND ".join(conditions)}
        GROUP BY model_name, coin, horizon_hours
        ORDER BY accuracy DESC
        """
        try:
            return pd.read_sql(query, self.engine)
        except Exception as e:
            logger.error(f"Accuracy query error: {e}")
            return pd.DataFrame()

    def get_overall_metrics(self):
        query = """
        SELECT
            COUNT(*) as total_predictions,
            SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) as correct,
            ROUND(AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) as accuracy,
            ROUND(AVG(confidence)::numeric, 4) as avg_confidence,
            COUNT(DISTINCT coin) as coins_tracked,
            MIN(predicted_at) as earliest_prediction,
            MAX(predicted_at) as latest_prediction
        FROM predictions
        WHERE was_correct IS NOT NULL
        """
        try:
            return pd.read_sql(query, self.engine)
        except Exception:
            return pd.DataFrame()
