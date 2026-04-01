"""
backtesting/paper_trader.py — Virtual paper trading simulator.

CRIT-05 FIX: Replaced NOW() (PostgreSQL-only) with datetime('now') (SQLite).
CRIT-06 FIX: All f-string SQL injections replaced with parameterized queries.
MED (paper_trades): Table added to init_db.py (LOW-04).
"""
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from database.connection import get_engine
from config.constants import INITIAL_CAPITAL, POSITION_SIZE_PCT
from sqlalchemy import text


class PaperTrader:
    """Live paper trading simulator that tracks virtual positions in the database."""

    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.engine = get_engine()
        self.capital = initial_capital

    def get_open_positions(self):
        try:
            return pd.read_sql(
                "SELECT * FROM paper_trades WHERE status = 'OPEN' ORDER BY opened_at ASC",
                self.engine
            )
        except Exception:
            return pd.DataFrame()

    def get_portfolio_value(self):
        open_pos = self.get_open_positions()
        total_value = self.capital
        for _, pos in open_pos.iterrows():
            # CRIT-06 FIX: use parameterized query, not f-string
            try:
                price_df = pd.read_sql(
                    "SELECT close FROM price_data WHERE coin = :coin ORDER BY timestamp DESC LIMIT 1",
                    self.engine,
                    params={"coin": pos["coin"]},
                )
                if not price_df.empty:
                    current_price = price_df.iloc[0]["close"]
                    total_value += pos["quantity"] * current_price
            except Exception:
                pass
        return total_value

    def open_position(self, coin, signal_id, confidence, price, capital_pct=POSITION_SIZE_PCT):
        position_size = self.capital * capital_pct * confidence
        quantity = position_size / price

        trade = {
            "coin": coin, "action": "BUY", "quantity": quantity,
            "entry_price": price, "signal_id": signal_id, "confidence": confidence,
            "status": "OPEN", "opened_at": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        }
        try:
            pd.DataFrame([trade]).to_sql("paper_trades", self.engine, if_exists="append", index=False)
            self.capital -= position_size
            logger.info(f"Paper trade opened: {coin} @ ${price:.2f}, qty={quantity:.6f}")
        except Exception as e:
            logger.error(f"Paper trade open error: {e}")

    def close_position(self, trade_id, close_price):
        try:
            # CRIT-06 FIX: use parameterized query
            open_pos = pd.read_sql(
                "SELECT * FROM paper_trades WHERE id = :tid AND status = 'OPEN'",
                self.engine,
                params={"tid": int(trade_id)},
            )
            if open_pos.empty:
                return

            pos = open_pos.iloc[0]
            pnl = float((close_price - pos["entry_price"]) * pos["quantity"])
            pnl_pct = float((close_price - pos["entry_price"]) / pos["entry_price"] * 100)
            self.capital += float(pos["quantity"]) * close_price
            closed_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

            # CRIT-05 FIX: datetime('now') for SQLite; fully parameterized (no f-strings)
            with self.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE paper_trades SET
                        exit_price = :ep, pnl = :pnl, pnl_pct = :ppc,
                        status = 'CLOSED', closed_at = :ca
                    WHERE id = :tid
                """), {"ep": float(close_price), "pnl": pnl, "ppc": pnl_pct,
                       "ca": closed_at, "tid": int(trade_id)})
                conn.commit()

            logger.info(f"Paper trade closed: id={trade_id}, PnL={pnl_pct:.2f}%")
        except Exception as e:
            logger.error(f"Paper trade close error: {e}")

    def get_performance_summary(self):
        try:
            # CRIT-05 FIX: removed ::numeric PostgreSQL cast; SQLite ROUND() is compatible
            return pd.read_sql("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
                    ROUND(SUM(pnl), 2) as total_pnl,
                    ROUND(MAX(pnl_pct), 2) as best_trade_pct,
                    ROUND(MIN(pnl_pct), 2) as worst_trade_pct
                FROM paper_trades WHERE status = 'CLOSED'
            """, self.engine)
        except Exception:
            return pd.DataFrame()
