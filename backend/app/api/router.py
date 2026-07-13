"""Central API router — assembles all domain routers under /api/v1.

Versioning policy:
  - /api/v1 is stable for the lifetime of V1.
  - Breaking changes require /api/v2.
  - Additive changes (new optional fields/endpoints) remain in /api/v1.
"""

from fastapi import APIRouter

from app.domains.auth.router import router as auth_router
from app.domains.inventory.router import router as inventory_router
from app.domains.master.router import router as master_router
from app.domains.reports.router import router as reports_router
from app.domains.requests.router import router as requests_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(master_router)
api_router.include_router(inventory_router)
api_router.include_router(requests_router)
api_router.include_router(reports_router)

# Future domain routers:
# api_router.include_router(settings_router)
# api_router.include_router(audit_router)
