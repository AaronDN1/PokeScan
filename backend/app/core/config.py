"""Environment-backed service configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings with safe local-development defaults."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="POKELENS_", extra="ignore")

    environment: str = "development"
    api_title: str = "PokéLens Recognition API"
    api_version: str = "0.1.0"
    database_url: str = "sqlite+aiosqlite:///./data/pokelens.db"
    redis_url: str | None = None
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    max_upload_bytes: int = 12 * 1024 * 1024
    max_image_pixels: int = 24_000_000
    min_blur_variance: float = 8.0
    recognition_rate_limit_per_minute: int = 30
    candidate_limit: int = 8
    auto_create_schema: bool = True
    development_diagnostics: bool = False
    pokemon_tcg_api_key: str | None = None
    tcgplayer_public_key: str | None = None
    tcgplayer_private_key: str | None = None
    tcgplayer_api_version: str = "v1.39.0"
    marketplace_cache_hours: int = 12
    ocr_backend: str = Field(
        default="paddle",
        validation_alias=AliasChoices("OCR_BACKEND", "POKELENS_OCR_BACKEND"),
    )
    artwork_matcher_backend: str = Field(
        default="composite",
        validation_alias=AliasChoices(
            "ARTWORK_MATCHER_BACKEND", "POKELENS_ARTWORK_MATCHER_BACKEND"
        ),
    )
    custom_onnx_models_required: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "CUSTOM_ONNX_MODELS_REQUIRED", "POKELENS_CUSTOM_ONNX_MODELS_REQUIRED"
        ),
    )
    rapidocr_model_type: str = "tiny"
    name_crop: tuple[float, float, float, float] = (0.035, 0.025, 0.78, 0.155)
    collector_crop: tuple[float, float, float, float] = (0.0, 0.88, 1.0, 0.995)
    artwork_crop: tuple[float, float, float, float] = (0.055, 0.135, 0.945, 0.675)
    name_ocr_model_path: Path = Path("models/ocr-name.onnx")
    number_ocr_model_path: Path = Path("models/ocr-number.onnx")
    artwork_model_path: Path = Path("models/artwork-embedding.onnx")
    pretrained_artwork_model_path: Path = Path("models/mobilenetv2-features.onnx")
    reference_assets_dir: Path = Path("data/reference-images")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return one immutable settings instance per process."""
    return Settings()
