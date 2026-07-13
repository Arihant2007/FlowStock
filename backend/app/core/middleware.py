"""HTTP middleware for the FMCG WMS application.

Middlewares applied (in order of registration):
  1. CorrelationIDMiddleware  — injects X-Correlation-ID and X-Request-ID
                               into structlog context for every request.
  2. AppExceptionMiddleware   — converts AppError subclasses into the
                               standard JSON error envelope.
"""

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import AppError
from app.core.logger import get_logger

logger = get_logger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Inject a correlation/request ID into every request context.

    - Reads X-Correlation-ID from the incoming request header (set by
      an upstream gateway) or generates a new UUID4.
    - Generates a unique X-Request-ID per request.
    - Binds both IDs into the structlog context so every log line
      emitted during that request contains them automatically.
    - Echoes both IDs back in the response headers.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request_id = str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_id=request_id,
        )

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        return response


class AppExceptionMiddleware(BaseHTTPMiddleware):
    """Translate AppError subclasses into the standard JSON error envelope."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            return await call_next(request)
        except AppError as exc:
            logger.warning(
                "application_error",
                code=exc.code,
                message=exc.message,
                status_code=exc.status_code,
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("unhandled_error", exc_info=exc)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "code": "APP_000",
                    "message": "An unexpected error occurred.",
                    "details": {},
                },
            )
