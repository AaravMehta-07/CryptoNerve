import os
import sys
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Reddit
    @property
    def REDDIT_CLIENT_ID(self):
        return os.getenv("REDDIT_CLIENT_ID")

    @property
    def REDDIT_CLIENT_SECRET(self):
        return os.getenv("REDDIT_CLIENT_SECRET")

    @property
    def REDDIT_USER_AGENT(self):
        return os.getenv("REDDIT_USER_AGENT", "crypto-sentinel:v1.0")

    # NewsAPI
    @property
    def NEWS_API_KEY(self):
        return os.getenv("NEWS_API_KEY")

    # Etherscan
    @property
    def ETHERSCAN_API_KEY(self):
        return os.getenv("ETHERSCAN_API_KEY")

    # Database — SQLite only
    @property
    def DATABASE_URL(self):
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "crypto_sentinel.db"
        )
        return f"sqlite:///{db_path}"

    # Local LLM (llama-cpp-python with GGUF)
    @property
    def LLM_MODEL_PATH(self):
        return os.getenv(
            "LLM_MODEL_PATH",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "models",
                "mistral-7b-instruct-v0.1.Q3_K_M.gguf",
            ),
        )

    @property
    def LLM_N_CTX(self):
        return int(os.getenv("LLM_N_CTX", "4096"))

    @property
    def LLM_N_GPU_LAYERS(self):
        return int(os.getenv("LLM_N_GPU_LAYERS", "0"))

    @property
    def LLM_N_THREADS(self):
        return int(os.getenv("LLM_N_THREADS", "8"))

    LLM_MODEL_NAME = "mistral-7b-instruct-v0.1-Q3_K_M"

    # Pipeline intervals (seconds)
    REDDIT_FETCH_INTERVAL = 300    # 5 minutes
    NEWS_FETCH_INTERVAL = 600      # 10 minutes
    PRICE_FETCH_INTERVAL = 60      # 1 minute
    ONCHAIN_FETCH_INTERVAL = 120   # 2 minutes
    SENTIMENT_PROCESS_INTERVAL = 600   # 10 minutes
    MODEL_RETRAIN_INTERVAL = 21600     # 6 hours
    SIGNAL_GENERATION_INTERVAL = 300   # 5 minutes

    # Model
    @property
    def MODEL_ARTIFACTS_DIR(self):
        # Portable model directory — copy this folder to transfer trained models
        default = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "trained_models",
        )
        return os.getenv("MODEL_ARTIFACTS_DIR", default)

    HISTORICAL_DAYS = 90
    PREDICTION_HORIZONS = [1, 4, 24]  # hours — models trained for each

    # Binance
    BINANCE_BASE_URL = "https://api.binance.com"

    def validate(self):
        """Warn about missing optional keys."""
        warnings = []
        if not self.REDDIT_CLIENT_ID or not self.REDDIT_CLIENT_SECRET:
            warnings.append(
                "  ⚠  REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set — Reddit collection disabled."
            )
        if not self.NEWS_API_KEY:
            warnings.append(
                "  ⚠  NEWS_API_KEY not set — falling back to CryptoCompare free feed."
            )
        if not self.ETHERSCAN_API_KEY:
            warnings.append(
                "  ⚠  ETHERSCAN_API_KEY not set — on-chain data collection disabled."
            )
        if warnings:
            print("=" * 60, file=sys.stderr)
            print("CRYPTO SENTINEL — CONFIG WARNINGS:", file=sys.stderr)
            for w in warnings:
                print(w, file=sys.stderr)
            print("=" * 60, file=sys.stderr)


settings = Settings()
settings.validate()
