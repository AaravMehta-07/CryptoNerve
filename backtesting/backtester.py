import pandas as pd
import numpy as np
from loguru import logger
from database.connection import get_engine
from config.constants import INITIAL_CAPITAL, POSITION_SIZE_PCT
import json
import uuid


class Backtester:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.engine = get_engine()

    def run_backtest(self, coin, days=30):
        signals_df = pd.read_sql(f"""
            SELECT signal_type, confidence, generated_at, price_at_signal,
                   sentiment_score, prediction_score, onchain_score, technical_score
            FROM signals
            WHERE coin = '{coin}' AND generated_at > NOW() - INTERVAL '{days} days'
            ORDER BY generated_at ASC
        """, self.engine)

        if signals_df.empty:
            logger.warning(f"No historical signals for {coin} backtest")
            return None

        prices_df = pd.read_sql(f"""
            SELECT timestamp, close FROM price_data
            WHERE coin = '{coin}' AND interval = '15m'
            AND timestamp > NOW() - INTERVAL '{days} days'
            ORDER BY timestamp ASC
        """, self.engine)

        if prices_df.empty:
            return None

        prices_df.set_index("timestamp", inplace=True)

        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = [{"timestamp": str(prices_df.index[0]), "equity": capital}]

        for _, signal in signals_df.iterrows():
            signal_type = signal["signal_type"]
            confidence = signal["confidence"]
            price = signal["price_at_signal"]

            if price is None or price == 0:
                continue

            position_size = capital * POSITION_SIZE_PCT * confidence

            if signal_type in ["BUY", "STRONG_BUY"] and position is None and confidence > 0.55:
                position = {
                    "entry_price": price,
                    "quantity": position_size / price,
                    "entry_time": signal["generated_at"],
                }
            elif signal_type in ["SELL", "STRONG_SELL"] and position is not None:
                pnl = (price - position["entry_price"]) * position["quantity"]
                pnl_pct = (price - position["entry_price"]) / position["entry_price"] * 100
                capital += pnl

                trades.append({
                    "entry_time": str(position["entry_time"]),
                    "exit_time": str(signal["generated_at"]),
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "quantity": position["quantity"],
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "result": "WIN" if pnl > 0 else "LOSS",
                })
                equity_curve.append({"timestamp": str(signal["generated_at"]), "equity": round(capital, 2)})
                position = None

        if not trades:
            return {"message": "No completed trades in period", "coin": coin}

        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        returns = [t["pnl_pct"] / 100 for t in trades]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0

        equity_values = [e["equity"] for e in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for val in equity_values:
            peak = max(peak, val)
            max_dd = max(max_dd, (peak - val) / peak * 100)

        total_wins = sum(t["pnl"] for t in winning_trades)
        total_losses = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        result = {
            "coin": coin, "period_days": days,
            "initial_capital": self.initial_capital, "final_capital": round(capital, 2),
            "total_return_pct": round((capital - self.initial_capital) / self.initial_capital * 100, 2),
            "sharpe_ratio": round(sharpe, 4), "max_drawdown_pct": round(max_dd, 2),
            "win_rate": round(len(winning_trades) / len(trades) * 100, 2),
            "total_trades": len(trades), "profit_factor": round(profit_factor, 2),
            "avg_win_pct": round(np.mean([t["pnl_pct"] for t in winning_trades]), 2) if winning_trades else 0,
            "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losing_trades]), 2) if losing_trades else 0,
            "equity_curve": equity_curve, "trades": trades,
        }

        try:
            save_record = {
                "run_id": str(uuid.uuid4())[:8], "coin": coin,
                "strategy_name": "ensemble_sentiment_onchain",
                "start_date": equity_curve[0]["timestamp"], "end_date": equity_curve[-1]["timestamp"],
                "initial_capital": result["initial_capital"], "final_capital": result["final_capital"],
                "total_return_pct": result["total_return_pct"], "sharpe_ratio": result["sharpe_ratio"],
                "max_drawdown_pct": result["max_drawdown_pct"], "win_rate": result["win_rate"],
                "total_trades": result["total_trades"], "profit_factor": result["profit_factor"],
                "avg_win_pct": result["avg_win_pct"], "avg_loss_pct": result["avg_loss_pct"],
                "equity_curve_json": json.dumps(equity_curve), "trades_json": json.dumps(trades),
            }
            pd.DataFrame([save_record]).to_sql("backtest_results", self.engine, if_exists="append", index=False)
        except Exception as e:
            logger.error(f"Backtest save error: {e}")

        return result
import pandas as pd
import numpy as np
from loguru import logger
from database.connection import get_engine
from config.constants import INITIAL_CAPITAL, POSITION_SIZE_PCT
import json
import uuid


class Backtester:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.engine = get_engine()

    def run_backtest(self, coin, days=30):
        signals_df = pd.read_sql(f"""
            SELECT signal_type, confidence, generated_at, price_at_signal,
                   sentiment_score, prediction_score, onchain_score, technical_score
            FROM signals
            WHERE coin = '{coin}' AND generated_at > NOW() - INTERVAL '{days} days'
            ORDER BY generated_at ASC
        """, self.engine)

        if signals_df.empty:
            logger.warning(f"No historical signals for {coin} backtest")
            return None

        prices_df = pd.read_sql(f"""
            SELECT timestamp, close FROM price_data
            WHERE coin = '{coin}' AND interval = '15m'
            AND timestamp > NOW() - INTERVAL '{days} days'
            ORDER BY timestamp ASC
        """, self.engine)

        if prices_df.empty:
            return None

        prices_df.set_index("timestamp", inplace=True)

        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = [{"timestamp": str(prices_df.index[0]), "equity": capital}]

        for _, signal in signals_df.iterrows():
            signal_type = signal["signal_type"]
            confidence = signal["confidence"]
            price = signal["price_at_signal"]

            if price is None or price == 0:
                continue

            position_size = capital * POSITION_SIZE_PCT * confidence

            if signal_type in ["BUY", "STRONG_BUY"] and position is None and confidence > 0.55:
                position = {
                    "entry_price": price,
                    "quantity": position_size / price,
                    "entry_time": signal["generated_at"],
                }
            elif signal_type in ["SELL", "STRONG_SELL"] and position is not None:
                pnl = (price - position["entry_price"]) * position["quantity"]
                pnl_pct = (price - position["entry_price"]) / position["entry_price"] * 100
                capital += pnl

                trades.append({
                    "entry_time": str(position["entry_time"]),
                    "exit_time": str(signal["generated_at"]),
                    "entry_price": position["entry_price"],
                    "exit_price": price,
                    "quantity": position["quantity"],
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "result": "WIN" if pnl > 0 else "LOSS",
                })
                equity_curve.append({"timestamp": str(signal["generated_at"]), "equity": round(capital, 2)})
                position = None

        if not trades:
            return {"message": "No completed trades in period", "coin": coin}

        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]
        returns = [t["pnl_pct"] / 100 for t in trades]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if len(returns) > 1 and np.std(returns) > 0 else 0

        equity_values = [e["equity"] for e in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for val in equity_values:
            peak = max(peak, val)
            max_dd = max(max_dd, (peak - val) / peak * 100)

        total_wins = sum(t["pnl"] for t in winning_trades)
        total_losses = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        result = {
            "coin": coin, "period_days": days,
            "initial_capital": self.initial_capital, "final_capital": round(capital, 2),
            "total_return_pct": round((capital - self.initial_capital) / self.initial_capital * 100, 2),
            "sharpe_ratio": round(sharpe, 4), "max_drawdown_pct": round(max_dd, 2),
            "win_rate": round(len(winning_trades) / len(trades) * 100, 2),
            "total_trades": len(trades), "profit_factor": round(profit_factor, 2),
            "avg_win_pct": round(np.mean([t["pnl_pct"] for t in winning_trades]), 2) if winning_trades else 0,
            "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losing_trades]), 2) if losing_trades else 0,
            "equity_curve": equity_curve, "trades": trades,
        }

        try:
            save_record = {
                "run_id": str(uuid.uuid4())[:8], "coin": coin,
                "strategy_name": "ensemble_sentiment_onchain",
                "start_date": equity_curve[0]["timestamp"], "end_date": equity_curve[-1]["timestamp"],
                "initial_capital": result["initial_capital"], "final_capital": result["final_capital"],
                "total_return_pct": result["total_return_pct"], "sharpe_ratio": result["sharpe_ratio"],
                "max_drawdown_pct": result["max_drawdown_pct"], "win_rate": result["win_rate"],
                "total_trades": result["total_trades"], "profit_factor": result["profit_factor"],
                "avg_win_pct": result["avg_win_pct"], "avg_loss_pct": result["avg_loss_pct"],
                "equity_curve_json": json.dumps(equity_curve), "trades_json": json.dumps(trades),
            }
            pd.DataFrame([save_record]).to_sql("backtest_results", self.engine, if_exists="append", index=False)
        except Exception as e:
            logger.error(f"Backtest save error: {e}")

        return result
