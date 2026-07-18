"""Environment-backed service configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="POKELENS_", extra="ignore")

    environment: str = "development"
    api_title: str = "PokéLens Recognition API"
    api_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./pokelens.db"
    redis_url: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )
    max_upload_bytes: int = 12 * 1024 * 1024
    max_image_pixels: int = 24_000_000
    min_blur_variance: float = 34.0
    recognition_rate_limit_per_minute: int = 30
    auto_create_schema: bool = True
    name_ocr_model_path: Path = Path("models/ocr-name.onnx")
    number_ocr_model_path: Path = Path("models/ocr-number.onnx")
    artwork_model_path: Path = Path("models/artwork-embedding.onnx")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""
    return Settings()
