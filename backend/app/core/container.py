"""Explicit dependency composition at the infrastructure boundary."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.application.confidence import WeightedConfidenceEngine
from app.application.recognize_card import RecognizeCard
from app.core.config import Settings
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import (
    SqlAlchemyCardRepository,
    SqlAlchemyFeedbackRepository,
    SqlAlchemyPriceProvider,
)
from app.infrastructure.imaging.opencv_locator import OpenCvCardLocator
from app.infrastructure.imaging.validator import PillowImageValidator
from app.infrastructure.models.onnx_artwork import OnnxArtworkMatcher
from app.infrastructure.models.onnx_ocr import OnnxCtcOcrEngine
from app.infrastructure.rate_limit import RecognitionRateLimiter


class Container:
    """Own process-wide adapters whose public surfaces are domain ports."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.cards = SqlAlchemyCardRepository(self.sessions)
        self.prices = SqlAlchemyPriceProvider(self.sessions)
        self.feedback = SqlAlchemyFeedbackRepository(self.sessions)
        self.rate_limiter = RecognitionRateLimiter(
            limit=settings.recognition_rate_limit_per_minute,
            redis_url=settings.redis_url,
        )
        self.recognize_card = RecognizeCard(
            validator=PillowImageValidator(
                max_bytes=settings.max_upload_bytes,
                max_pixels=settings.max_image_pixels,
            ),
            locator=OpenCvCardLocator(minimum_blur_variance=settings.min_blur_variance),
            ocr=OnnxCtcOcrEngine(
                name_model_path=settings.name_ocr_model_path,
                number_model_path=settings.number_ocr_model_path,
            ),
            cards=self.cards,
            artwork=OnnxArtworkMatcher(settings.artwork_model_path),
            prices=self.prices,
            confidence=WeightedConfidenceEngine(),
        )

    async def start(self) -> None:
        """Create the local schema when explicitly enabled."""
        if self.settings.auto_create_schema:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Release database and cache resources."""
        await self.rate_limiter.close()
        await self.engine.dispose()
