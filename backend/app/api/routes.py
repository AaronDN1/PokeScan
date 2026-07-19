"""Versioned recognition, card, pricing, feedback, and health routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, or_, select, text, union

from app.api.schemas import (
    CardResponse,
    CatalogCapability,
    FeedbackRequest,
    HealthCapabilities,
    HealthResponse,
    PriceResponse,
    PricingCapability,
    RecognitionResponse,
)
from app.core.container import Container
from app.infrastructure.database.models import PriceRecord, TcgPlayerQuoteRecord

router = APIRouter()


def _container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


@router.post("/api/v1/recognitions", response_model=RecognitionResponse)
async def recognize_card(
    request: Request,
    image: Annotated[UploadFile, File(description="One clear photo containing one Pokémon card")],
    debug: Annotated[
        bool, Query(description="Include development-only recognition diagnostics")
    ] = False,
) -> RecognitionResponse:
    """Identify exactly one uploaded card and delete request bytes after processing."""
    container = _container(request)
    client_key = request.client.host if request.client else "unknown"
    if not await container.rate_limiter.allow(client_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many scans. Try again in a minute.",
        )
    payload = await image.read(container.settings.max_upload_bytes + 1)
    try:
        result = await container.recognize_card.execute(
            payload=payload,
            declared_mime=image.content_type or "application/octet-stream",
            include_diagnostics=(
                debug
                and container.settings.environment == "development"
                and container.settings.development_diagnostics
            ),
        )
        return RecognitionResponse.from_domain(result)
    finally:
        payload = b""
        await image.close()


@router.get("/api/v1/cards/{card_id}", response_model=CardResponse)
async def get_card(card_id: str, request: Request) -> CardResponse:
    """Return one normalized catalog card with its cached price."""
    container = _container(request)
    card = await container.cards.get(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    price = await container.prices.get_price(card)
    return CardResponse.from_domain(card, price)


@router.get("/api/v1/prices/{card_id}", response_model=PriceResponse)
async def get_price(card_id: str, request: Request) -> PriceResponse:
    """Return cached marketplace data, refreshing it when stale and available."""
    container = _container(request)
    card = await container.cards.get(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found.")
    return PriceResponse.from_domain(await container.prices.get_price(card))


@router.post(
    "/api/v1/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def submit_feedback(feedback: FeedbackRequest, request: Request) -> Response:
    """Persist an explicit correction without retaining the original photo."""
    await _container(request).feedback.record(**feedback.model_dump())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Report independent recognition, catalog, and pricing capabilities."""
    container = _container(request)
    database_status = "ready"
    priced_card_count = 0
    try:
        async with container.sessions() as session:
            await session.execute(text("SELECT 1"))
            priced_ids = union(
                select(PriceRecord.card_id).where(PriceRecord.amount.is_not(None)),
                select(TcgPlayerQuoteRecord.card_id).where(
                    or_(
                        TcgPlayerQuoteRecord.market_price.is_not(None),
                        TcgPlayerQuoteRecord.near_mint.is_not(None),
                        TcgPlayerQuoteRecord.lightly_played.is_not(None),
                        TcgPlayerQuoteRecord.moderately_played.is_not(None),
                    )
                ),
            ).subquery()
            priced_card_count = int(
                await session.scalar(select(func.count()).select_from(priced_ids)) or 0
            )
    except Exception:
        database_status = "unavailable"
    settings = container.settings
    ocr_ready = container.ocr_backend != "unavailable"
    artwork_ready = bool(getattr(container.artwork, "available", False))
    catalog_ready = database_status == "ready" and container.catalog_count > 0
    recognition_ready = ocr_ready and artwork_ready and catalog_ready
    issues = list(dict.fromkeys(container.component_errors.values()))
    if not catalog_ready and database_status == "ready":
        issues.append("The local card catalog is empty. Run the development bootstrap.")
    return HealthResponse(
        status="ready" if recognition_ready else "degraded",
        version=settings.api_version,
        database=database_status,
        recognition_ready=recognition_ready,
        capabilities=HealthCapabilities(
            card_localization={"ready": True, "backend": "opencv"},
            ocr={"ready": ocr_ready, "backend": container.ocr_backend},
            artwork_matching={
                "ready": artwork_ready,
                "backend": container.artwork_backend,
            },
            catalog=CatalogCapability(
                ready=catalog_ready,
                card_count=container.catalog_count,
                source="tcgdex",
            ),
            pricing=PricingCapability(
                ready=database_status == "ready",
                priced_card_count=priced_card_count,
                mode=(
                    "official_tcgplayer_api"
                    if container.prices.official_condition_pricing_available
                    else "direct_links_and_public_market"
                ),
                direct_links_ready=True,
                condition_prices_ready=container.prices.official_condition_pricing_available,
            ),
            custom_onnx_models=container.settings.custom_onnx_models_required,
        ),
        issues=issues,
    )
