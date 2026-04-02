
# 🛡️ Crypto Sentinel



> Track 5 coins in real-time with Reddit/news sentiment (local Mistral 7B via llama-cpp-python), on-chain whale intelligence, XGBoost/Prophet/LSTM ensemble predictions, and composite trading signals — all on your own hardware. No cloud LLM fees.

---

## 🏗️ Architecture

```
Reddit/News → Sentiment (Mistral 7B GGUF + FinBERT) ↘
Binance OHLCV → Technical Indicators (40+ features)  → Ensemble Signals → Streamlit Dashboard
Etherscan On-Chain → Whale Flow Analysis              ↗
```

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed
- 8GB+ RAM (16GB recommended for Mistral 7B)
- GPU optional but recommended (CUDA 12 supported)
- Python 3.10+ (if running without Docker)

### 1. Clone & Configure
```bash
git clone https://github.com/AaravMehta-07/CryptoNerve
cd CryptoNerve
cp .env.example .env
# Edit .env with your API keys (Reddit, NewsAPI, Etherscan)
```

### 2. Download the GGUF Model
The GGUF model (~3.5 GB) is **not included** in this repo (excluded via `.gitignore`).  
Place it at `models/mistral-7b-instruct-v0.1.Q3_K_M.gguf` or set the `LLM_MODEL_PATH` env variable.

You can download it from [TheBloke on HuggingFace](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.1-GGUF).

### 3. Start Everything
```bash
docker compose up -d
```

### 4. Open Dashboard
```
http://localhost:8501
```

### Running Without Docker
```bash
pip install -r requirements.txt
python -m pipeline  # or python orchestrator.py
streamlit run dashboard/app.py
```

> **Note:** `llama-cpp-python` requires a C++ compiler. For GPU support:  
> `CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python==0.2.90`

---

## 🔑 API Keys Required

| Service | Free Tier | Use |
|---------|-----------|-----|
| [Reddit](https://www.reddit.com/prefs/apps) | Yes | Social sentiment |
| [NewsAPI](https://newsapi.org) | 100 req/day | News sentiment |
| [Etherscan](https://etherscan.io/apis) | 5 req/sec | Whale tracking |

All keys are optional — the system degrades gracefully with warnings if any are missing.

---

## 📊 Dashboard Pages

| Page | Description |
|------|-------------|
| 📊 Live Dashboard | Multi-coin price cards, Fear & Greed, real-time signals |
| 📈 Price & Technicals | OHLCV + RSI + MACD + Bollinger Bands |
| 💬 Sentiment Analysis | Sentiment timeline, FUD/bullish composition, narrative detection |
| 🐋 On-Chain Intelligence | Whale flows, exchange inflow/outflow, accumulation detection |
| 🤖 AI Predictions | Ensemble prediction history with accuracy tracking |
| ⚡ Signals & Alerts | Full signal breakdown with component scores |
| ⏳ Backtesting | Strategy backtest with equity curve, Sharpe ratio, drawdown |
| 📝 AI Reports | LLM-generated market reports (Mistral 7B) |
| 🔍 Explainability | SHAP waterfall + feature importance visualization |
| 📊 Model Performance | Accuracy tracking across models, coins, horizons |

---

## ⚙️ Pipeline Schedule

| Interval | Task |
|----------|------|
| 1 min | Price data (Binance) |
| 2 min | On-chain whale data (Etherscan) |
| 5 min | Reddit posts (PRAW) + Signal generation |
| 10 min | News articles (NewsAPI / CryptoCompare) + Sentiment analysis |
| 6 hours | Model retraining |

---

## 🔬 ML Models & Stack

| Model | Weight | Role |
|-------|--------|------|
| XGBoost | 45% | Primary classifier with 40+ features incl. sentiment + technical + on-chain |
| Prophet | 30% | Time-series trend, seasonality, holiday effects |
| LSTM | 25% | Sequential patterns via 48-step sliding window |

**Additional ML:** LightGBM, AutoGluon (tabular), Optuna hyperparameter optimization, SHAP explainability.

**NLP:** Mistral 7B (GGUF, CPU/GPU via llama-cpp-python) + FinBERT for financial sentiment.

---

## 📦 Key Dependencies

```
# ML
xgboost, lightgbm, tensorflow, scikit-learn, autogluon, optuna, shap

# NLP / LLM
transformers, torch, llama-cpp-python (GGUF)

# Data / On-chain
praw, newsapi-python, web3, aiohttp

# Dashboard
streamlit, plotly, wordcloud

# DB
psycopg2, sqlalchemy (PostgreSQL with connection pooling)
```

---

## ⚠️ Disclaimer

**This is for educational purposes only. Not financial advice.**  
Crypto markets are highly volatile. Never invest more than you can afford to lose.

---
*Crypto Sentinel v1.1 — Built with ❤️ using Python, Streamlit, PostgreSQL, and llama-cpp-python*
