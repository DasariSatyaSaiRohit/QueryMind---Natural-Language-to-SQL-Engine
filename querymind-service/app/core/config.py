from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "QueryMind Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database (Service-owned PostgreSQL)
    DATABASE_URL: str 

    # Redis
    REDIS_URL: str
    SCHEMA_CACHE_TTL: int = 86400   # 24h
    QUERY_CACHE_TTL: int = 86400    # 24h
    SESSION_CACHE_TTL: int = 3600   # 1h

    # RabbitMQ
    RABBITMQ_URL: str 
    HISTORY_QUEUE: str = "history-persist-queue"
    HISTORY_DLQ: str = "history-persist-dlq"
    MESSAGE_EXPIRATION_MS: int = 300000  # 5 minutes

    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # AI
    AI_PROVIDER: str = "ollama"
    OLLAMA_URL: str 
    OLLAMA_MODEL: str = "llama3.1:8b"
    GEMINI_API_KEY: str    
    # settings.py
    GEMINI_MODEL:str = "gemini-2.5-flash-lite"
    USE_GEMINI: bool = True
   # settings.py
    HF_API_KEY: str 
    HF_MODEL_ID: str = "defog/sqlcoder-7b-2"
    HF_MODEL_URL: str 
    WARMUP_MODEL_ON_STARTUP: bool = True

    # Query limits
    MAX_RESULT_ROWS: int = 1000
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 200
    CONNECTION_TIMEOUT: int = 10
    QUERY_TIMEOUT: int = 30

    # Encryption
    ENCRYPTION_KEY: str

    @property
    def is_debug(self) -> bool:
        return self.LOG_LEVEL == "DEBUG" or self.DEBUG


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
