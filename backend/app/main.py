"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.container import Container
from app.core.logging import configure_logging
from app.domain.errors import RecognitionError

settings = get_settings()
configure_logging(development=settings.environment == "development")
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Build and release process-wide infrastructure dependencies."""
    container = Container(settings)
    await container.start()
    application.state.container = container
    try:
        yield
    finally:
        await container.close()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)
app.include_router(router)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Attach a request id and record structured total timing without payloads."""
    request_id = request.headers.get("x-request-id", str(uuid4()))[:80]
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", request_id=request_id, path=request.url.path)
        raise
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "no-referrer"
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        total_ms=round((perf_counter() - started) * 1000, 2),
    )
    return response


@app.exception_handler(RecognitionError)
async def recognition_error_handler(_request: Request, error: RecognitionError) -> JSONResponse:
    """Translate expected domain errors without exposing raw exceptions."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(error), "code": error.code},
    )
