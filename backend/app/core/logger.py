"""Structured JSON logger with correlation ID support.

Every log event emits a JSON object containing:
  - timestamp, level, message, logger, correlation_id, request_id
  - any additional key=value pairs passed at the call site

Usage:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("inventory_reserved", material_id=42, qty="100.0000")
"""

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Bootstrap structlog and stdlib logging.

    Call once at application startup inside the lifespan handler.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    if sys.stdout.encoding != "utf-8" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        # Emit compact JSON in production for log aggregation pipelines.
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Emit human-readable coloured output during development.
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
