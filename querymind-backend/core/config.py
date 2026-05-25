from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Server
    PORT: int = 8001
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Security
    JWT_SECRET: str = Field(..., description="Secret key for JWT verification")
    ENCRYPTION_KEY: str = Field(..., description="Fernet key for encrypting DB connection strings")
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key")
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 2048

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    SCHEMA_CACHE_TTL: int = 3600
    QUERY_CACHE_TTL: int = 86400
    SESSION_TTL: int = 86400

    # RabbitMQ (Celery broker only)
    AMQP_URL: str = "amqp://guest:guest@localhost:5672/"

    # Database pool (per session engine)
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 3
    DB_POOL_TIMEOUT: int = 10
    DB_POOL_RECYCLE: int = 1800

    # Execution safety
    STATEMENT_TIMEOUT_MS: int = 30000
    MAX_RESULT_ROWS: int = 1000

    # RAG
    MAX_RELEVANT_TABLES: int = 10

    # WebSocket
    WS_GENERATION_TIMEOUT: int = 120


settings = Settings()
