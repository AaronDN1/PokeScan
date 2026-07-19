"""Explicit dependency composition at the infrastructure boundary."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.application.confidence import WeightedConfidenceEngine
from app.application.recognize_card import RecognizeCard
from app.core.config import Settings
from app.domain.errors import RecognitionUnavailableError
from app.domain.models import Card, OcrReading
from app.domain.ports import ArtworkMatcher, OcrEngine, VisualCandidateFinder
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import (
    SqlAlchemyCardRepository,
    SqlAlchemyFeedbackRepository,
)
from app.infrastructure.imaging.opencv_locator import OpenCvCardLocator
from app.infrastructure.imaging.orientation import OcrOrientationResolver
from app.infrastructure.imaging.regions import RegionCrops
from app.infrastructure.imaging.validator import PillowImageValidator
from app.infrastructure.marketplace.provider import CachedMarketplacePriceProvider
from app.infrastructure.marketplace.tcgplayer import (
    PokemonTcgMarketplaceResolver,
    TcgPlayerConditionClient,
)
from app.infrastructure.models.composite_artwork import CompositeArtworkMatcher
from app.infrastructure.models.onnx_artwork import OnnxArtworkMatcher
from app.infrastructure.models.onnx_ocr import OnnxCtcOcrEngine
from app.infrastructure.models.paddle_ocr import PaddleOcrEngine
from app.infrastructure.models.visual_index import CatalogVisualCandidateFinder
from app.infrastructure.rate_limit import RecognitionRateLimiter


class _UnavailableOcrEngine:
    """Keep health reachable when OCR setup is incomplete."""

    def __init__(self, message: str) -> None:
        self._message = message

    def read_name(self, _region_jpeg: bytes) -> OcrReading:
        raise RecognitionUnavailableError(self._message)

    def read_collector_number(self, _region_jpeg: bytes) -> OcrReading:
        raise RecognitionUnavailableError(self._message)


class _NoVisualCandidates:
    """Disable global visual retrieval for custom matchers without shared features."""

    async def search(self, _card_jpeg: bytes, *, limit: int) -> Sequence[Card]:
        del limit
        return ()


class Container:
    """Own process-wide adapters whose public surfaces are domain ports."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.database_url.startswith("sqlite+aiosqlite:///./"):
            sqlite_path = Path(settings.database_url.removeprefix("sqlite+aiosqlite:///"))
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.cards = SqlAlchemyCardRepository(self.sessions)
        self.prices = CachedMarketplacePriceProvider(
            self.sessions,
            PokemonTcgMarketplaceResolver(api_key=settings.pokemon_tcg_api_key),
            TcgPlayerConditionClient(
                public_key=settings.tcgplayer_public_key,
                private_key=settings.tcgplayer_private_key,
                api_version=settings.tcgplayer_api_version,
            ),
            cache_hours=settings.marketplace_cache_hours,
        )
        self.feedback = SqlAlchemyFeedbackRepository(self.sessions)
        self.rate_limiter = RecognitionRateLimiter(
            limit=settings.recognition_rate_limit_per_minute,
            redis_url=settings.redis_url,
        )
        self.component_errors: dict[str, str] = {}
        crops = RegionCrops(
            name=settings.name_crop,
            collector=settings.collector_crop,
            artwork=settings.artwork_crop,
        )
        ocr, self.ocr_backend = self._build_ocr()
        artwork, self.artwork_backend = self._build_artwork()
        self.artwork = artwork
        self.visual_candidates: VisualCandidateFinder
        if isinstance(artwork, CompositeArtworkMatcher):
            self.visual_candidates = CatalogVisualCandidateFinder(
                self.sessions,
                self.cards,
                artwork,
            )
        else:
            self.visual_candidates = _NoVisualCandidates()
        self.recognize_card = RecognizeCard(
            validator=PillowImageValidator(
                max_bytes=settings.max_upload_bytes,
                max_pixels=settings.max_image_pixels,
            ),
            locator=OpenCvCardLocator(
                minimum_blur_variance=settings.min_blur_variance,
                crops=crops,
            ),
            orientation=OcrOrientationResolver(ocr, crops),
            cards=self.cards,
            visual_candidates=self.visual_candidates,
            artwork=artwork,
            prices=self.prices,
            confidence=WeightedConfidenceEngine(),
            candidate_limit=settings.candidate_limit,
        )
        self.catalog_count = 0

    def _build_ocr(self) -> tuple[OcrEngine, str]:
        backend = self.settings.ocr_backend.casefold()
        try:
            if backend == "paddle":
                return (
                    PaddleOcrEngine(model_type=self.settings.rapidocr_model_type),
                    PaddleOcrEngine.backend_name,
                )
            if backend == "onnx_ctc":
                required = (
                    self.settings.name_ocr_model_path,
                    self.settings.number_ocr_model_path,
                )
                if self.settings.custom_onnx_models_required and not all(
                    path.is_file() for path in required
                ):
                    raise RecognitionUnavailableError("Required custom OCR models are missing.")
                return (
                    OnnxCtcOcrEngine(
                        name_model_path=self.settings.name_ocr_model_path,
                        number_model_path=self.settings.number_ocr_model_path,
                    ),
                    "custom_onnx_ctc",
                )
            raise RecognitionUnavailableError(f"Unsupported OCR backend: {backend}")
        except RecognitionUnavailableError as error:
            self.component_errors["ocr"] = str(error)
            return _UnavailableOcrEngine(str(error)), "unavailable"

    def _build_artwork(self) -> tuple[ArtworkMatcher, str]:
        backend = self.settings.artwork_matcher_backend.casefold()
        if backend == "composite":
            matcher = CompositeArtworkMatcher(self.settings.pretrained_artwork_model_path)
            if not matcher.available:
                self.component_errors["artwork_embedding"] = (
                    "The MobileNetV2 feature model is missing. Run bootstrap_dev.py."
                )
            return matcher, matcher.backend_name
        if backend == "onnx_embedding":
            if (
                self.settings.custom_onnx_models_required
                and not self.settings.artwork_model_path.is_file()
            ):
                self.component_errors["artwork"] = "Required custom artwork model is missing."
            return OnnxArtworkMatcher(self.settings.artwork_model_path), "custom_onnx_embedding"
        self.component_errors["artwork"] = f"Unsupported artwork matcher backend: {backend}"
        matcher = CompositeArtworkMatcher(self.settings.pretrained_artwork_model_path)
        return matcher, "unavailable"

    async def start(self) -> None:
        """Create the local schema and cache catalog capability counts."""
        if self.settings.auto_create_schema:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        try:
            self.catalog_count = await self.cards.count()
            if isinstance(self.visual_candidates, CatalogVisualCandidateFinder):
                await self.visual_candidates.start()
        except Exception:
            self.component_errors["database"] = "The catalog database is unavailable."
            self.catalog_count = 0

    async def close(self) -> None:
        """Release database and cache resources."""
        await self.rate_limiter.close()
        await self.prices.close()
        await self.engine.dispose()
