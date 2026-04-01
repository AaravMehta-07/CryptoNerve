# 🛡️ Crypto Sentinel

**Self-hosted LLM-powered crypto sentiment & price prediction terminal**

> Track 5 coins in real-time with Reddit/news sentiment (Mistral 7B via Ollama), on-chain whale intelligence, XGBoost/Prophet/LSTM ensemble predictions, and composite trading signals — all on your own hardware.

---

## 🏗️ Architecture

```
Reddit/News → Sentiment (Mistral 7B + FinBERT) ↘
Binance OHLCV → Technical Indicators           → Ensemble Signals → Streamlit Dashboard
Etherscan On-Chain → Whale Flow Analysis       ↗
```

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed
- 8GB+ RAM (16GB recommended for Mistral 7B)
- GPU optional but recommended for Ollama

### 1. Clone & Configure
```bash
git clone <repo>
cd crypto-sentinel
cp .env.example .env
# Edit .env with your API keys (Reddit, NewsAPI, Etherscan)
```

### 2. Start Everything
```bash
docker compose up -d
# First run pulls Mistral 7B (~4GB) — wait 10-15 minutes
```

### 3. Open Dashboard
```
http://localhost:8501
```

## 🔑 API Keys Required

| Service | Free Tier | Use |
|---------|-----------|-----|
| [Reddit](https://www.reddit.com/prefs/apps) | Yes | Social sentiment |
| [NewsAPI](https://newsapi.org) | 100 req/day | News sentiment |
| [Etherscan](https://etherscan.io/apis) | 5 req/sec | Whale tracking |

## 📊 Dashboard Pages

| Page | Description |
|------|-------------|
| 📊 Live Dashboard | Multi-coin price cards, Fear & Greed, real-time signals |
| 📈 Price & Technicals | OHLCV + RSI + MACD + Bollinger Bands |
| 💬 Sentiment Analysis | Sentiment timeline, FUD/bullish composition, narratives |
| 🐋 On-Chain Intelligence | Whale flows, exchange inflow/outflow, accumulation detection |
| 🤖 AI Predictions | Ensemble prediction history with accuracy tracking |
| ⚡ Signals & Alerts | Full signal breakdown with component scores |
| ⏳ Backtesting | Strategy backtest with equity curve, Sharpe, drawdown |
| 📝 AI Reports | LLM-generated market reports (Mistral 7B) |
| 🔍 Explainability | SHAP waterfall + feature importance visualization |
| 📊 Model Performance | Accuracy tracking across models, coins, horizons |

## ⚙️ Pipeline

The pipeline runs automatically on a schedule:
- Every **1 min**: Price data (Binance)
- Every **2 min**: On-chain whale data (Etherscan)
- Every **5 min**: Reddit posts (PRAW)
- Every **10 min**: News articles (NewsAPI / CryptoCompare)
- Every **3 min**: Sentiment analysis (Mistral 7B)
- Every **5 min**: Signal generation
- Every **1 hour**: Model retraining

## 🔬 ML Models

| Model | Role | Features |
|-------|------|----------|
| XGBoost | Primary classifier (45%) | 40+ features incl. sentiment + technical + on-chain |
| Prophet | Time-series trend (30%) | Price seasonality, trend, holiday effects |
| LSTM | Sequential patterns (25%) | 48-step sliding window across all features |

## ⚠️ Disclaimer

**This is for educational purposes only. Not financial advice.**
Crypto markets are highly volatile. Never invest more than you can afford to lose.

---
*Crypto Sentinel v1.0 — Built with ❤️ using Python, Streamlit, PostgreSQL, and Ollama*
