"""Admin domain router — user and role management endpoints.

Endpoints:
  GET    /admin/users                        — List users (paginated + filters)
  GET    /admin/users/{user_id}              — Full user detail
  POST   /admin/users                        — Create user
  PATCH  /admin/users/{user_id}              — Edit user profile (no password)
  POST   /admin/users/{user_id}/reset-password — Generate temp password
  POST   /admin/users/{user_id}/lock         — Admin-impose lock
  POST   /admin/users/{user_id}/unlock       — Remove admin lock
  POST   /admin/users/{user_id}/activate     — Activate user
  POST   /admin/users/{user_id}/deactivate   — Deactivate user
  GET    /admin/roles                        — List roles for dropdowns
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.responses import ok, paginate
from app.domains.admin.schemas import (
    CreateUserAdminRequest,
    ResetPasswordResponse,
    RoleOut,
    UpdateUserAdminRequest,
    UserAdminOut,
    UserListOut,
)
from app.domains.admin.service import AdminService
from app.domains.auth.dependencies import get_current_user, require_permission
from app.domains.auth.models import User
from app.infrastructure.database import get_db

router = APIRouter(prefix="/admin", tags=["Administration"])


# ---------------------------------------------------------------------------
# Users — listing & detail
# ---------------------------------------------------------------------------


@router.get("/users", response_model=dict, status_code=status.HTTP_200_OK)
def list_users(
    search: Optional[str] = Query(None, description="Search full name, username, or email."),
    role_public_id: Optional[uuid.UUID] = Query(None, description="Filter by role."),
    warehouse_public_id: Optional[uuid.UUID] = Query(None, description="Filter by warehouse."),
    is_active: Optional[bool] = Query(None, description="Filter by active status."),
    is_locked: Optional[bool] = Query(None, description="Filter by admin lock status."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> dict:
    """List all users with optional filters and pagination."""
    svc = AdminService(db)

    # Resolve role_public_id → role_id
    role_id: Optional[int] = None
    if role_public_id is not None:
        from sqlalchemy import select
        from app.domains.auth.models import Role
        role = db.scalar(select(Role).where(Role.public_id == role_public_id))
        if role:
            role_id = role.id

    # Resolve warehouse_public_id → warehouse_id
    warehouse_id: Optional[int] = None
    if warehouse_public_id is not None:
        from sqlalchemy import select
        from app.domains.master.models import Warehouse
        wh = db.scalar(select(Warehouse).where(Warehouse.public_id == warehouse_public_id))
        if wh:
            warehouse_id = wh.id

    users, total = svc.list_users(
        search=search,
        role_id=role_id,
        warehouse_id=warehouse_id,
        is_active=is_active,
        is_locked=is_locked,
        page=page,
        page_size=page_size,
    )
    return paginate(
        [u.model_dump() for u in users],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/users/stats", response_model=dict, status_code=status.HTTP_200_OK)
def get_user_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> dict:
    """Return KPI counts: total, active, locked, admins."""
    stats = AdminService(db).get_stats()
    return ok(stats)


@router.get("/users/{user_id}", response_model=dict, status_code=status.HTTP_200_OK)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> dict:
    """Return full admin detail for a specific user."""
    user = AdminService(db).get_user(user_id)
    return ok(user.model_dump())


# ---------------------------------------------------------------------------
# Users — create & edit
# ---------------------------------------------------------------------------


@router.post("/users", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserAdminRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> dict:
    """Create a new user. Returns user and generated temporary password."""
    user_out, temp_password = AdminService(db).create_user(payload, admin_id=current_user.id)
    db.commit()
    return ok(
        {
            "user": user_out.model_dump(),
            "temporary_password": temp_password
        },
        message="User created successfully. Show the temporary password to the user once."
    )


@router.patch("/users/{user_id}", response_model=dict, status_code=status.HTTP_200_OK)
def update_user(
    user_id: uuid.UUID,
    payload: UpdateUserAdminRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> dict:
    """Edit user profile fields. Password is never in this payload."""
    user = AdminService(db).update_user(user_id, payload, admin_id=current_user.id)
    db.commit()
    return ok(user.model_dump(), message="User updated successfully.")


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/reset-password",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
def reset_password(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> dict:
    """Generate a one-time temporary password for the user.

    The plain-text password is returned ONCE in this response.
    After this call, it cannot be retrieved again — only the hash is stored.
    The user must change their password on next login (must_change_password=True).
    """
    result = AdminService(db).reset_password(user_id, admin_id=current_user.id)
    db.commit()
    return ok(
        result.model_dump(),
        message="Temporary password generated. Show it to the user once and securely.",
    )


# ---------------------------------------------------------------------------
# Activate / Deactivate
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/activate", response_model=dict, status_code=status.HTTP_200_OK
)
def activate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> dict:
    """Activate a deactivated user account."""
    user = AdminService(db).activate_user(user_id, admin_id=current_user.id)
    db.commit()
    return ok(user.model_dump(), message="User activated.")


@router.post(
    "/users/{user_id}/deactivate", response_model=dict, status_code=status.HTTP_200_OK
)
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:manage")),
) -> dict:
    """Deactivate a user and revoke all their active sessions."""
    user = AdminService(db).deactivate_user(user_id, admin_id=current_user.id)
    db.commit()
    return ok(user.model_dump(), message="User deactivated.")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=dict, status_code=status.HTTP_200_OK)
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> dict:
    """Return all active roles for admin dropdowns."""
    roles = AdminService(db).list_roles()
    return ok([r.model_dump() for r in roles])
