"""Application settings loaded from environment variables (and .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for KeeperPilot.

    Values come from environment variables or the root `.env` file.
    See `.env.example` for the full list.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://keeperpilot:keeperpilot@localhost:5432/keeperpilot"

    # AI Agent
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # KeeperHub execution layer
    keeperhub_mock: bool = True
    keeperhub_api_key: str = ""
    keeperhub_mcp_url: str = "https://app.keeperhub.com/mcp"
    keeperhub_api_base: str = "https://app.keeperhub.com/api"
    keeperhub_chain_id: str = "11155111"  # Ethereum Sepolia

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Auth (JWT)
    # Dev-only default (>=32 bytes to satisfy HS256). Override with a long
    # random value in every real deployment.
    jwt_secret: str = "dev-only-insecure-jwt-secret-change-me-please-32-bytes-min"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24  # 24h

    # Wallet ownership challenge
    challenge_ttl_minutes: int = 10

    # Frontend
    next_public_api_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
