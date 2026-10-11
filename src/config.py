from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "production"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    timezone: str = "UTC"

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "oggy_bot"
    db_user: str = "oggy"
    db_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # -------------------------------------------------------------------------
    # YouTube Data API v3
    # -------------------------------------------------------------------------
    youtube_api_key: str
    youtube_channel_ids: str = ""

    @property
    def youtube_channels(self) -> list[str]:
        return [c.strip() for c in self.youtube_channel_ids.split(",") if c.strip()]

    # -------------------------------------------------------------------------
    # Instagram Graph API
    # -------------------------------------------------------------------------
    ig_app_id: str
    ig_app_secret: str
    ig_access_token: str
    ig_user_id: str
    ig_page_id: str

    # -------------------------------------------------------------------------
    # LLM Configuration
    # -------------------------------------------------------------------------
    llm_provider: Literal["openai", "anthropic", "ollama"] = "openai"
    llm_api_key: str
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None

    # -------------------------------------------------------------------------
    # Video Storage (S3-compatible)
    # -------------------------------------------------------------------------
    storage_provider: Literal["r2", "s3", "local"] = "r2"
    storage_endpoint: str
    storage_access_key: str
    storage_secret_key: str
    storage_bucket: str
    storage_public_url: str

    # -------------------------------------------------------------------------
    # Video Processing
    # -------------------------------------------------------------------------
    clip_min_duration: int = 15
    clip_max_duration: int = 60
    clips_per_source: int = 3
    target_resolution: str = "1080x1920"
    target_fps: int = 30
    video_crf: int = 22
    watermark_path: str | None = None
    watermark_opacity: float = 0.3

    @property
    def target_width(self) -> int:
        return int(self.target_resolution.split("x")[0])

    @property
    def target_height(self) -> int:
        return int(self.target_resolution.split("x")[1])

    # -------------------------------------------------------------------------
    # Scheduling
    # -------------------------------------------------------------------------
    discovery_schedule: str = "0 */6 * * *"
    posting_schedule: str = "0 9,14,19 * * *"
    cleanup_schedule: str = "0 3 * * *"

    # -------------------------------------------------------------------------
    # Rate Limits & Safety
    # -------------------------------------------------------------------------
    max_posts_per_day: int = 3
    min_hours_between_posts: int = 4
    max_source_video_age_days: int = 30
    keep_clips_days: int = 60
    keep_source_videos_days: int = 7

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------
    sentry_dsn: str | None = None
    healthchecks_io_url: str | None = None

    # -------------------------------------------------------------------------
    # Paths
    # -------------------------------------------------------------------------
    data_dir: Path = Path("/app/data")
    logs_dir: Path = Path("/app/logs")
    temp_dir: Path = Path("/app/temp")

    @field_validator("data_dir", "logs_dir", "temp_dir", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()