from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

JobRunner = Literal["eager", "thread", "dramatiq"]


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

    # Number of sentences per practice group.
    group_size: int = Field(default=10, ge=1, le=50)

    # How media jobs are executed when submitted from an API route:
    #   eager    -> run synchronously inside the request (used in tests)
    #   thread   -> run in a background daemon thread (default for local dev)
    #   dramatiq -> enqueue to the Redis-backed Dramatiq worker (production)
    job_runner: JobRunner = "thread"

    # faster-whisper transcription settings.
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    # Zhipu (智谱) LLM for keyword analysis. When the key is unset the pipeline
    # falls back to the naive stopword-based extractor in practice.domain.
    zhipu_api_key: str | None = None
    zhipu_model: str = "glm-4-flash"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    keyword_batch_size: int = Field(default=30, ge=1, le=100)

    # Single-user authentication. Credentials come from the environment; login
    # issues a JWT signed with secret_key. Change these in your .env.
    auth_username: str = "admin"
    auth_password: str = "listenflow"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=60 * 24 * 7, ge=1)  # 7 days


@lru_cache
def get_settings() -> Settings:
    return Settings()
