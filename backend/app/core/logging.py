"""Structured logging configured for machine-readable production output."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, development: bool) -> None:
    """Configure standard logging and structlog without image payload fields."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer(colors=False)
        if development
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
