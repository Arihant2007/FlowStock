"""FMCG WMS FastAPI application factory.

Creates and configures the FastAPI application with:
  - Structured logging
  - CORS middleware
  - Correlation ID and exception handling middleware
  - Rate limiting (slowapi) on auth endpoints
  - Prometheus metrics
  - All domain routers
  - OpenAPI / Swagger with Bearer token authorization
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logger import configure_logging
from app.core.middleware import AppExceptionMiddleware, CorrelationIDMiddleware

settings = get_settings()

# Rate limiter keyed by client IP address.
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler — runs startup and shutdown logic."""
    configure_logging()
    yield


def create_app() -> FastAPI:
    """Construct and return the configured FastAPI application."""
    app = FastAPI(
        title="FMCG WMS — Inventory Transfer System",
        description=(
            "Production inventory management system for ODS ↔ RMPM "
            "material transfers in an FMCG manufacturing plant.\n\n"
            "**Authentication:** Use the `/api/v1/auth/login` endpoint to obtain a Bearer token, "
            "then click the **Authorize** button above and paste the `access_token`."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # --- Rate limiting ---
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # --- Middleware (outermost registered last) ---
    app.add_middleware(AppExceptionMiddleware)
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Prometheus metrics at /metrics ---
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # --- Routers ---
    app.include_router(health_router)
    app.include_router(api_router)

    # --- Swagger security scheme ---
    # Override the generated OpenAPI schema to add a BearerAuth security definition
    # so the "Authorize" button appears at the top of Swagger UI.

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})[
            "BearerAuth"
        ] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste your access token here.",
        }
        # Apply security globally — individual endpoints can override with [].
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    return app


app = create_app()
