# 🛡️ Crypto Sentinel — AI Market Intelligence Terminal

> **Self-hosted LLM-powered crypto sentiment & price prediction terminal**  
> Real-time market intelligence for BTC, ETH, SOL, XRP, DOGE powered by ensemble ML models, LLM sentiment analysis via Ollama (Mistral 7B), on-chain whale tracking, and composite trading signals.

**🏆 NMIMS Innovathon 2026 — Hackathon Project**

![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)
![Ollama](https://img.shields.io/badge/Ollama-Mistral_7B-FF6F61)
![SQLite](https://img.shields.io/badge/SQLite-Local_DB-003B57?logo=sqlite)

---

## 🏗️ Architecture

```
Binance API     → Live OHLCV + Price Feeds     ╲
NewsAPI / RSS   → News Articles → Ollama LLM    → Composite Signal Engine → React Dashboard
Etherscan API   → Whale / On-Chain Flows        ╱        ↑
                                                    XGBoost + LSTM + AutoGluon
                                                    Ensemble ML Predictions
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 + Vite + Recharts |
| **Backend** | FastAPI (Python) + Uvicorn |
| **ML Models** | XGBoost, LSTM (TensorFlow), AutoGluon |
| **LLM** | Ollama → Mistral 7B Instruct (Q4_K_M) |
| **Database** | SQLite (local, zero-config) |
| **Data** | Binance, NewsAPI, CryptoCompare, Etherscan |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Ollama** installed with `mistral:7b-instruct-q4_K_M` model
- 8GB+ RAM (16GB recommended)
- GPU optional but recommended (GTX 1650+ for Ollama)

### 1. Clone & Install

```bash
git clone https://github.com/AaravMehta-07/CryptoNerve.git
cd CryptoNerve

# Backend dependencies
cd crypto-sentinel
pip install -r requirements.txt

# Frontend dependencies
cd ../crypto-sentinel-ui
npm install
```

### 2. Configure API Keys

```bash
cd crypto-sentinel
cp .env.example .env
# Edit .env with your API keys
```

### 3. Start Ollama

```bash
ollama pull mistral:7b-instruct-q4_K_M
ollama serve
```

### 4. Launch Everything

```bash
cd crypto-sentinel-ui
npm run dev
```

This starts both the **React UI** (port 5173) and the **FastAPI backend** (port 8000) concurrently.

### 5. Open Dashboard

```
http://localhost:5173
```

---

## 📊 Dashboard Pages

| Page | Description |
|------|-------------|
| ⚡ **Live Dashboard** | Multi-coin price ticker, Fear & Greed Index, real-time signal cards, market overview |
| 📡 **Signals & Alerts** | Composite signal breakdown with radar chart (Sentiment × Tech × ML × On-Chain), confidence gating, multi-timeframe signal matrix (1h/4h/24h) |
| 💬 **Sentiment Analysis** | Hourly sentiment timeline, bullish/bearish heatmap, narrative detection, news feed with LLM analysis |
| 📈 **Price & Technicals** | OHLCV candlestick charts, RSI, MACD, Bollinger Bands, technical overlays |
| 🐋 **On-Chain Intel** | Whale transaction log, exchange flow analysis, accumulation/distribution detection |
| 🤖 **AI Predictions** | ML ensemble predictions with confidence gating, model validation accuracy chart, win/loss tracking |
| 📊 **Model Performance** | Real validation accuracy across XGBoost/LSTM/AutoGluon/Ensemble, per-coin per-horizon breakdown |
| ⏳ **Backtesting** | Strategy backtest with equity curve, Sharpe ratio, max drawdown, PnL analysis |
| 📝 **AI Reports** | LLM-generated daily market intelligence reports via Ollama Mistral 7B |

---

## 🔬 ML Pipeline

### Ensemble Models

| Model | Role | Best Accuracy |
|-------|------|--------------|
| **XGBoost** | Gradient-boosted tree classifier with 40+ engineered features | 70.4% (DOGE 24h) |
| **LSTM** | 48-step sequential pattern detector (TensorFlow/Keras) | 69.2% (XRP 24h) |
| **AutoGluon** | AutoML tabular learner with automatic feature selection | 70.4% (DOGE 24h) |
| **Ensemble** | Weighted vote across all models with confidence calibration | 64.8% (DOGE 24h) |

### Signal Generation

Composite signals are generated using a weighted multi-factor scoring system:

| Factor | Weight | Source |
|--------|--------|--------|
| Sentiment | 50% | Ollama LLM analysis of 700+ news articles |
| Technicals | 25% | RSI + MACD + Bollinger Bands with confluence detection |
| On-Chain | 15% | Whale flow analysis from Etherscan |
| ML Prediction | 10% | Ensemble model directional forecast |

### Confidence Gating

Only predictions with **>55% confidence** generate actionable BUY/SELL signals. Lower-confidence predictions are marked as **NO TRADE** to improve win rate.

---

## ⚙️ Data Pipeline

| Interval | Task |
|----------|------|
| Real-time | Price data from Binance WebSocket |
| 5 min | Technical indicator computation |
| 10 min | News scraping (NewsAPI / CryptoCompare) |
| 10 min | Signal generation + prediction |
| On-demand | LLM sentiment analysis (Ollama) |
| 6 hours | Model retraining |

---

## 🔑 API Keys

| Service | Free Tier | Purpose |
|---------|-----------|---------|
| [Binance](https://www.binance.com) | Yes | OHLCV price data |
| [NewsAPI](https://newsapi.org) | 100 req/day | News headlines |
| [CryptoCompare](https://cryptocompare.com) | Yes | Additional news feed |
| [Etherscan](https://etherscan.io/apis) | 5 req/sec | On-chain whale tracking |

All keys are optional — the system degrades gracefully with warnings.

---

## 📁 Project Structure

```
CryptoNerve/
├── crypto-sentinel/            # Backend
│   ├── api/main.py             # FastAPI endpoints (75+ routes)
│   ├── ingestion/              # Data collectors (Binance, News, On-chain)
│   ├── models/                 # ML model training (XGBoost, LSTM, AutoGluon)
│   ├── sentiment/              # LLM sentiment engine (Ollama integration)
│   ├── signals/                # Composite signal generator
│   ├── features/               # Feature engineering (40+ indicators)
│   ├── database/               # SQLite connection & schema
│   ├── trained_models/         # Serialized model artifacts
│   ├── scripts/                # Utility & maintenance scripts
│   └── data/                   # SQLite database
│
├── crypto-sentinel-ui/         # Frontend
│   ├── src/pages/              # React page components
│   ├── src/components/         # Shared UI components
│   ├── src/utils/              # API client & formatters
│   └── vite.config.js          # Vite + API proxy config
│
└── start.bat                   # Windows one-click launcher
```

---

## 🖥️ Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | i5-8300H | i7-10750H+ |
| RAM | 8 GB | 16 GB |
| GPU | — | GTX 1650+ (for Ollama) |
| Storage | 2 GB | 5 GB |

---

## ⚠️ Disclaimer

**This is for educational and hackathon purposes only. Not financial advice.**  
Crypto markets are highly volatile. Never invest more than you can afford to lose. All predictions are experimental and should not be used for actual trading decisions.

---

*Crypto Sentinel v1.0 — Built with ❤️ for NMIMS Innovathon 2026*  
*Python • React • FastAPI • XGBoost • LSTM • AutoGluon • Ollama Mistral 7B*
