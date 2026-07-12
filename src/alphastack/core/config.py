"""AlphaStack configuration via Pydantic Settings."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "alphastack"
    user: str = "alphastack"
    password: SecretStr = SecretStr("alphastack")
    pool_size: int = 20
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False

    @property
    def async_url(self) -> str:
        pw = self.password.get_secret_value()
        return f"postgresql+asyncpg://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        pw = self.password.get_secret_value()
        return f"postgresql+psycopg2://{self.user}:{pw}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None
    ssl: bool = False
    pool_size: int = 20
    stream_max_len: int = 100_000
    cache_default_ttl: int = 300  # seconds

    @property
    def url(self) -> str:
        scheme = "rediss" if self.ssl else "redis"
        auth = ""
        if self.password:
            auth = f":{self.password.get_secret_value()}@"
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"


class MT5Settings(BaseSettings):
    """MetaTrader 5 broker credentials."""

    model_config = SettingsConfigDict(env_prefix="MT5_")

    login: int = 0
    password: SecretStr = SecretStr("")
    server: str = ""
    path: str = ""  # Path to terminal64.exe
    timeout: int = 60_000  # ms


class CCXTSettings(BaseSettings):
    """CCXT exchange credentials."""

    model_config = SettingsConfigDict(env_prefix="CCXT_")

    exchange: str = "binance"
    api_key: SecretStr = SecretStr("")
    secret: SecretStr = SecretStr("")
    passphrase: SecretStr | None = None
    sandbox: bool = False


class LLMSettings(BaseSettings):
    """LLM / AI service keys."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    default_model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 4096


class DataFeedSettings(BaseSettings):
    """Market data feed API keys."""

    model_config = SettingsConfigDict(env_prefix="FEED_")

    polygon_api_key: SecretStr | None = None
    alpha_vantage_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None


class RiskSettings(BaseSettings):
    """Risk management parameters."""

    model_config = SettingsConfigDict(env_prefix="RISK_")

    max_drawdown_pct: float = Field(default=15.0, ge=0, le=100)
    max_position_size_pct: float = Field(default=5.0, ge=0, le=100)
    max_daily_loss_pct: float = Field(default=3.0, ge=0, le=100)
    max_open_positions: int = Field(default=10, ge=1)
    max_correlation: float = Field(default=0.7, ge=0, le=1)
    max_leverage: float = Field(default=2.0, ge=1)
    stop_loss_atr_multiplier: float = Field(default=2.0, ge=0.1)
    risk_free_rate: float = Field(default=0.05, ge=0)


class APISettings(BaseSettings):
    """FastAPI server settings."""

    model_config = SettingsConfigDict(env_prefix="API_")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    cors_origins: list[str] = ["http://localhost:3000"]
    api_prefix: str = "/api/v1"
    debug: bool = False


class Settings(BaseSettings):
    """Root settings – compose all sub-settings."""

    model_config = SettingsConfigDict(
        env_prefix="ALPHASTACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = Environment.DEV
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    mt5: MT5Settings = Field(default_factory=MT5Settings)
    ccxt: CCXTSettings = Field(default_factory=CCXTSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    feeds: DataFeedSettings = Field(default_factory=DataFeedSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    api: APISettings = Field(default_factory=APISettings)

    @field_validator("env", mode="before")
    @classmethod
    def _coerce_env(cls, v: Any) -> Environment:
        if isinstance(v, str):
            return Environment(v.lower())
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    return Settings()
