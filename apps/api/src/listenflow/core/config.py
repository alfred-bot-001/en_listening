from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LISTENFLOW_",
        extra="ignore",
    )

    env: str = "development"
    database_url: str = (
        "postgresql+psycopg://listenflow:listenflow@localhost:15432/listenflow"
    )
    redis_url: str = "redis://localhost:16379/0"
    storage_root: Path = Path("./storage")
    secret_key: str = Field(default="change-me")
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
