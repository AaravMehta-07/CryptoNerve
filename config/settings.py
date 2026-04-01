import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Reddit
    REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
    REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
    REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "crypto-sentinel:v1.0")

    # NewsAPI
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")

    # Etherscan
    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "crypto_sentinel")
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "sentinel_secure_2026")

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Local LLM (llama-cpp-python with GGUF)
    LLM_MODEL_PATH = os.getenv(
        "LLM_MODEL_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models",
            "mistral-7b-instruct-v0.1.Q3_K_M.gguf",
        ),
    )
    # n_ctx: token context window; n_gpu_layers: -1 = all layers on GPU (0 = CPU only)
    LLM_N_CTX = int(os.getenv("LLM_N_CTX", "4096"))
    LLM_N_GPU_LAYERS = int(os.getenv("LLM_N_GPU_LAYERS", "0"))   # set -1 if you have a GPU
    LLM_N_THREADS = int(os.getenv("LLM_N_THREADS", "8"))
    LLM_MODEL_NAME = "mistral-7b-instruct-v0.1-Q3_K_M"

    # Pipeline intervals (seconds)
    REDDIT_FETCH_INTERVAL = 300   # 5 minutes
    NEWS_FETCH_INTERVAL = 600     # 10 minutes
    PRICE_FETCH_INTERVAL = 60     # 1 minute
    ONCHAIN_FETCH_INTERVAL = 120  # 2 minutes
    SENTIMENT_PROCESS_INTERVAL = 180   # 3 minutes
    MODEL_RETRAIN_INTERVAL = 3600      # 1 hour
    SIGNAL_GENERATION_INTERVAL = 300   # 5 minutes

    # Model
    MODEL_ARTIFACTS_DIR = os.getenv("MODEL_ARTIFACTS_DIR", "./model_artifacts")
    HISTORICAL_DAYS = 90
    PREDICTION_HORIZONS = [1, 4, 24]  # hours

    # Binance
    BINANCE_BASE_URL = "https://api.binance.com"


settings = Settings()
