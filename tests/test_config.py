from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_loads_from_env(monkeypatch):
    """Test that settings load from environment variables."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DB_PASSWORD", "testpass")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")
    monkeypatch.setenv("YOUTUBE_CHANNEL_IDS", "UC123,UC456")
    monkeypatch.setenv("IG_APP_ID", "app_id")
    monkeypatch.setenv("IG_APP_SECRET", "app_secret")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "access_token")
    monkeypatch.setenv("IG_USER_ID", "user_id")
    monkeypatch.setenv("IG_PAGE_ID", "page_id")
    monkeypatch.setenv("LLM_API_KEY", "llm_key")
    monkeypatch.setenv("STORAGE_ENDPOINT", "https://test.r2.cloudflarestorage.com")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "access")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "secret")
    monkeypatch.setenv("STORAGE_BUCKET", "bucket")
    monkeypatch.setenv("STORAGE_PUBLIC_URL", "https://pub.test.r2.dev")

    settings = Settings()

    assert settings.app_env == "development"
    assert settings.log_level == "DEBUG"
    assert settings.db_password == "testpass"
    assert settings.youtube_api_key == "test_key"
    assert settings.youtube_channels == ["UC123", "UC456"]
    assert settings.ig_app_id == "app_id"
    assert settings.llm_api_key == "llm_key"


def test_database_url_properties(monkeypatch):
    """Test database URL construction."""
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "testdb")
    monkeypatch.setenv("DB_USER", "testuser")
    monkeypatch.setenv("DB_PASSWORD", "testpass")
    # Required for validation
    monkeypatch.setenv("YOUTUBE_API_KEY", "x")
    monkeypatch.setenv("YOUTUBE_CHANNEL_IDS", "UC123")
    monkeypatch.setenv("IG_APP_ID", "x")
    monkeypatch.setenv("IG_APP_SECRET", "x")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "x")
    monkeypatch.setenv("IG_USER_ID", "x")
    monkeypatch.setenv("IG_PAGE_ID", "x")
    monkeypatch.setenv("LLM_API_KEY", "x")
    monkeypatch.setenv("STORAGE_ENDPOINT", "x")
    monkeypatch.setenv("STORAGE_ACCESS_KEY", "x")
    monkeypatch.setenv("STORAGE_SECRET_KEY", "x")
    monkeypatch.setenv("STORAGE_BUCKET", "x")
    monkeypatch.setenv("STORAGE_PUBLIC_URL", "x")

    settings = Settings()

    assert settings.database_url == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
    assert settings.sync_database_url == "postgresql://testuser:testpass@localhost:5432/testdb"


def test_redis_url(monkeypatch):
    """Test Redis URL construction."""
    monkeypatch.setenv("REDIS_HOST", "redis")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_DB", "1")
    monkeypatch.setenv("REDIS_PASSWORD", "redispass")
    # Required
    for k, v in {
        "DB_PASSWORD": "x", "YOUTUBE_API_KEY": "x", "YOUTUBE_CHANNEL_IDS": "UC123",
        "IG_APP_ID": "x", "IG_APP_SECRET": "x", "IG_ACCESS_TOKEN": "x",
        "IG_USER_ID": "x", "IG_PAGE_ID": "x", "LLM_API_KEY": "x",
        "STORAGE_ENDPOINT": "x", "STORAGE_ACCESS_KEY": "x", "STORAGE_SECRET_KEY": "x",
        "STORAGE_BUCKET": "x", "STORAGE_PUBLIC_URL": "x",
    }.items():
        monkeypatch.setenv(k, v)

    settings = Settings()
    assert settings.redis_url == "redis://:redispass@redis:6379/1"


def test_target_resolution_parsing(monkeypatch):
    """Test target resolution width/height properties."""
    for k, v in {
        "DB_PASSWORD": "x", "YOUTUBE_API_KEY": "x", "YOUTUBE_CHANNEL_IDS": "UC123",
        "IG_APP_ID": "x", "IG_APP_SECRET": "x", "IG_ACCESS_TOKEN": "x",
        "IG_USER_ID": "x", "IG_PAGE_ID": "x", "LLM_API_KEY": "x",
        "STORAGE_ENDPOINT": "x", "STORAGE_ACCESS_KEY": "x", "STORAGE_SECRET_KEY": "x",
        "STORAGE_BUCKET": "x", "STORAGE_PUBLIC_URL": "x",
        "TARGET_RESOLUTION": "720x1280",
    }.items():
        monkeypatch.setenv(k, v)

    settings = Settings()
    assert settings.target_width == 720
    assert settings.target_height == 1280


def test_youtube_channels_empty_string(monkeypatch):
    """Test empty channel IDs returns empty list."""
    for k, v in {
        "DB_PASSWORD": "x", "YOUTUBE_API_KEY": "x", "YOUTUBE_CHANNEL_IDS": "",
        "IG_APP_ID": "x", "IG_APP_SECRET": "x", "IG_ACCESS_TOKEN": "x",
        "IG_USER_ID": "x", "IG_PAGE_ID": "x", "LLM_API_KEY": "x",
        "STORAGE_ENDPOINT": "x", "STORAGE_ACCESS_KEY": "x", "STORAGE_SECRET_KEY": "x",
        "STORAGE_BUCKET": "x", "STORAGE_PUBLIC_URL": "x",
    }.items():
        monkeypatch.setenv(k, v)

    settings = Settings()
    assert settings.youtube_channels == []


def test_missing_required_raises(monkeypatch):
    """Test that missing required fields raises ValidationError."""
    monkeypatch.setenv("DB_PASSWORD", "x")
    # Missing YOUTUBE_API_KEY

    with pytest.raises(ValidationError):
        Settings()