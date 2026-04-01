import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger
from database.connection import get_engine
from database.sql_compat import time_ago
from sqlalchemy import text


class AccuracyTracker:
    def __init__(self):
        self.engine = get_engine()

    def update_prediction_outcomes(self):
        # Use Python to filter: predicted_at < now - horizon_hours
        query = """
        SELECT p.id, p.coin, p.predicted_at, p.horizon_hours, p.predicted_direction
        FROM predictions p
        WHERE p.actual_direction IS NULL
        LIMIT 200
        """
        try:
            predictions = pd.read_sql(query, self.engine)
            if predictions.empty:
                return 0

            updated = 0
            now_utc = datetime.utcnow()
            for _, pred in predictions.iterrows():
                try:
                    predicted_at_dt = pd.Timestamp(pred["predicted_at"]).to_pydatetime().replace(tzinfo=None)
                except Exception:
                    continue
                horizon_h = int(pred["horizon_hours"] or 4)
                if predicted_at_dt + timedelta(hours=horizon_h) > now_utc:
                    continue  # horizon not yet passed
                target_time = predicted_at_dt + timedelta(hours=horizon_h)

                coin_sym = str(pred["coin"])
                t_pred_str = predicted_at_dt.strftime('%Y-%m-%d %H:%M:%S')
                t_tgt_str = target_time.strftime('%Y-%m-%d %H:%M:%S')
                price_query = text("""
                SELECT
                    (SELECT close FROM price_data
                     WHERE coin = :coin AND timestamp <= :tpred
                     ORDER BY timestamp DESC LIMIT 1) as price_at_prediction,
                    (SELECT close FROM price_data
                     WHERE coin = :coin AND timestamp <= :ttgt
                     ORDER BY timestamp DESC LIMIT 1) as price_at_target
                """)
                with self.engine.connect() as qconn:
                    prices = pd.read_sql(price_query, qconn,
                        params={"coin": coin_sym, "tpred": t_pred_str, "ttgt": t_tgt_str})
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

                now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                with self.engine.connect() as conn:
                    conn.execute(text("""
                        UPDATE predictions
                        SET actual_direction = :ad,
                            actual_price_change_pct = :acp,
                            was_correct = :wc,
                            outcome_recorded_at = :ts
                        WHERE id = :pid
                    """), {"ad": actual_direction,
                           "acp": float(actual_change * 100),
                           "wc": int(was_correct),
                           "ts": now_str,
                           "pid": int(pred["id"])})
                    conn.commit()
                updated += 1

            logger.info(f"Updated {updated} prediction outcomes")
            return updated
        except Exception as e:
            logger.error(f"Accuracy tracking error: {e}")
            return 0

    def get_model_accuracy(self, model_name=None, coin=None, horizon_hours=None):
        # HIGH-07 FIX: Use parameterized queries instead of f-string SQL injection
        conditions = ["was_correct IS NOT NULL"]
        params = {}
        if model_name:
            conditions.append("model_name = :model_name")
            params["model_name"] = model_name
        if coin:
            conditions.append("coin = :coin")
            params["coin"] = coin
        if horizon_hours:
            conditions.append("horizon_hours = :horizon_hours")
            params["horizon_hours"] = horizon_hours

        query = f"""
        SELECT
            model_name, coin, horizon_hours,
            COUNT(*) as total_predictions,
            SUM(CASE WHEN was_correct=1 THEN 1 ELSE 0 END) as correct_predictions,
            ROUND(AVG(CASE WHEN was_correct=1 THEN 1.0 ELSE 0.0 END), 4) as accuracy,
            ROUND(AVG(confidence), 4) as avg_confidence
        FROM predictions
        WHERE {" AND ".join(conditions)}
        GROUP BY model_name, coin, horizon_hours
        ORDER BY accuracy DESC
        """
        try:
            return pd.read_sql(text(query), self.engine, params=params)
        except Exception as e:
            logger.error(f"Accuracy query error: {e}")
            return pd.DataFrame()

    def get_overall_metrics(self):
        query = """
        SELECT
            COUNT(*) as total_predictions,
            SUM(CASE WHEN was_correct=1 THEN 1 ELSE 0 END) as correct,
            ROUND(AVG(CASE WHEN was_correct=1 THEN 1.0 ELSE 0.0 END), 4) as accuracy,
            ROUND(AVG(confidence), 4) as avg_confidence,
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
