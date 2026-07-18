"""Versioned recognition, card, pricing, feedback, and health routes."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy import text

from app.api.schemas import (
    CardResponse,
    FeedbackRequest,
    HealthResponse,
    PriceResponse,
    RecognitionResponse,
)
from app.core.container import Container

router = APIRouter()


def _container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


@router.post("/api/v1/recognitions", response_model=RecognitionResponse)
async def recognize_card(
    request: Request,
    image: Annotated[UploadFile, File(description="One clear photo containing one Pokémon card")],
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
    """Return the latest cached price without calling a marketplace inline."""
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
    """Report API, database, and model-artifact readiness."""
    container = _container(request)
    database_status = "ready"
    try:
        async with container.sessions() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    settings = container.settings
    models_ready = all(
        path.is_file()
        for path in (
            settings.name_ocr_model_path,
            settings.number_ocr_model_path,
            settings.artwork_model_path,
        )
    )
    return HealthResponse(
        status="ready" if database_status == "ready" else "degraded",
        version=settings.api_version,
        database=database_status,
        models="ready" if models_ready else "artifacts_required",
    )
