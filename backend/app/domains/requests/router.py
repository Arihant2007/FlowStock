"""Requests domain router — REST endpoints for the material request lifecycle.

Endpoints:
  POST /requests/preview           — Preview material request requirements
  POST /requests                   — Create a new SUBMITTED request
  GET  /requests                   — List requests (paginated)
  GET  /requests/{id}              — Get a request by ID
  PUT  /requests/{id}/approve      — SUBMITTED -> APPROVED (with reservation)
  POST /requests/{id}/dispatch     — APPROVED -> DISPATCHED (with transfer out)
  POST /requests/{id}/receive      — DISPATCHED -> RECEIVED (with transfer in)
  POST /requests/{id}/close        — RECEIVED -> CLOSED
  POST /requests/{id}/reject       — SUBMITTED -> REJECTED
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.responses import ok, paginate
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.master.models import Warehouse
from app.domains.requests.models import MaterialRequest
from app.domains.requests.schemas import (
    ApproveRequestPayload,
    CreateRequestPayload,
    MaterialRequestListItem,
    MaterialRequestOut,
    RequestPreviewPayload,
)
from app.domains.requests.service import RequestService
from app.infrastructure.database import get_db

router = APIRouter(prefix="/requests", tags=["Material Requests"])


@router.post("/preview", response_model=dict, status_code=status.HTTP_200_OK)
def preview_request(
    payload: RequestPreviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:create")),
) -> dict:
    """Preview material requirements based on active BOM and current ODS stock."""
    svc = RequestService(db)
    result = svc.preview_request(payload)
    return ok(result.model_dump(), message="Preview generated successfully.")


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: CreateRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:create")),
) -> dict:
    """Create a new material request.

    Starts in SUBMITTED state. Net required quantities are calculated using
    the active BOM and current ODS stock.
    """
    svc = RequestService(db)
    request = svc.create_request(payload, created_by=current_user.id)
    db.commit()
    # Refetch fully loaded
    loaded = svc._get_request(request.id)
    return ok(
        MaterialRequestOut.model_validate(loaded).model_dump(),
        message="Request created and submitted.",
    )


@router.get("", response_model=dict, status_code=status.HTTP_200_OK)
def list_requests(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("requests:read")),
) -> dict:
    """List material requests (paginated)."""
    from sqlalchemy import func

    stmt = select(MaterialRequest).order_by(MaterialRequest.created_at.desc())
    total: int = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())

    return paginate(
        [MaterialRequestListItem.model_validate(r).model_dump() for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{request_id}", response_model=dict, status_code=status.HTTP_200_OK)
def get_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("requests:read")),
) -> dict:
    """Get full details of a material request by public ID."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    loaded = RequestService(db)._get_request(req.id)
    # The output schema expects material fields per item.
    # They are not stored directly in MaterialRequestItem, so we augment the ORM objects.
    for sku in loaded.skus:
        for item in sku.items:
            if hasattr(item, "material") and item.material:
                item.material_public_id = item.material.public_id  # type: ignore[attr-defined]
                item.material_name = item.material.name            # type: ignore[attr-defined]
                item.material_code = item.material.code            # type: ignore[attr-defined]
                item.material_type = item.material.material_type.name if item.material.material_type else "RM"  # type: ignore[attr-defined]
            else:
                item.material_type = "RM"  # type: ignore[attr-defined]

    return ok(MaterialRequestOut.model_validate(loaded).model_dump())


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------


@router.put(
    "/{request_id}/approve", response_model=dict, status_code=status.HTTP_200_OK
)
def approve_request(
    request_id: uuid.UUID,
    payload: ApproveRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:approve")),
) -> dict:
    """Approve a request and execute inventory reservation."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    rmpm_wh = db.scalar(
        select(Warehouse).where(Warehouse.public_id == payload.rmpm_warehouse_public_id)
    )

    if not rmpm_wh:
        raise NotFoundError("Warehouse not found.")

    res = RequestService(db).approve_request(
        req.id,
        payload,
        approved_by=current_user.id,
        rmpm_warehouse_id=rmpm_wh.id,
    )
    db.commit()
    return ok({"status": res.status}, message=f"Request {res.status}.")


@router.post(
    "/{request_id}/dispatch", response_model=dict, status_code=status.HTTP_200_OK
)
def dispatch_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:approve")),
) -> dict:
    """Mark a request as DISPATCHED."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    res = RequestService(db).dispatch_request(req.id, dispatched_by=current_user.id)
    db.commit()
    return ok({"status": res.status}, message="Request dispatched.")


@router.post(
    "/{request_id}/receive", response_model=dict, status_code=status.HTTP_200_OK
)
def receive_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:create")),
) -> dict:
    """Mark a request as RECEIVED (by ODS)."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    res = RequestService(db).receive_request(req.id, received_by=current_user.id)
    db.commit()
    return ok({"status": res.status}, message="Request received.")


@router.post("/{request_id}/close", response_model=dict, status_code=status.HTTP_200_OK)
def close_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:create")),
) -> dict:
    """Mark a request as CLOSED."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    res = RequestService(db).close_request(req.id, closed_by=current_user.id)
    db.commit()
    return ok({"status": res.status}, message="Request closed.")


@router.post(
    "/{request_id}/reject", response_model=dict, status_code=status.HTTP_200_OK
)
def reject_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("requests:approve")),
) -> dict:
    """Mark a request as REJECTED."""
    req = db.scalar(
        select(MaterialRequest).where(MaterialRequest.public_id == request_id)
    )
    if not req:
        raise NotFoundError(f"Request {request_id} not found.")

    res = RequestService(db).reject_request(req.id, rejected_by=current_user.id)
    db.commit()
    return ok({"status": res.status}, message="Request rejected.")
