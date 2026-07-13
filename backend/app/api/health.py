"""Health and readiness endpoints for Render deployment checks.

/health — Liveness probe: returns 200 if the process is running.
/ready  — Readiness probe: returns 200 only if DB is reachable.
/metrics — Prometheus metrics endpoint (via prometheus-fastapi-instrumentator).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.infrastructure.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> dict:
    """Liveness probe — returns 200 if the process is alive."""
    return ok({"status": "ok"}, message="Service is alive.")


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    """Readiness probe — verifies database connectivity."""
    db.execute(text("SELECT 1"))
    return ok({"status": "ready", "database": "connected"}, message="Service is ready.")
