"""Auth domain router — validates input and delegates to AuthService.

Endpoints:
  POST /auth/login          — Authenticate with username/email + password.
  POST /auth/login/token    — OAuth2 password flow (for Swagger UI Authorize button).
  POST /auth/refresh        — Rotate refresh token.
  POST /auth/logout         — Revoke current refresh token.
  POST /auth/logout-all     — Revoke all sessions (password change, compromise).
  GET  /auth/me             — Return the authenticated user's profile.
  POST /auth/users          — Create a new user (admin-only).
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.domains.auth.dependencies import get_current_user, require_permission
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)
from app.domains.auth.service import AuthService
from app.infrastructure.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _extract_client_info(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post("/login", response_model=dict, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Authenticate with username or email and password; receive JWT tokens."""
    ip, ua = _extract_client_info(request)
    tokens = AuthService(db).login(
        payload.identifier,
        payload.password,
        ip_address=ip,
        user_agent=ua,
    )
    db.commit()
    return ok(tokens.model_dump(), message="Login successful.")


@router.post(
    "/login/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,  # Internal Swagger OAuth2 flow endpoint.
)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password flow — used by Swagger UI Authorize button only."""
    ip, ua = _extract_client_info(request) if request else (None, None)
    tokens = AuthService(db).login(
        form.username,
        form.password,
        ip_address=ip,
        user_agent=ua,
    )
    db.commit()
    return tokens


@router.post("/refresh", response_model=dict, status_code=status.HTTP_200_OK)
def refresh(
    payload: RefreshRequest, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    ip, ua = _extract_client_info(request)
    tokens = AuthService(db).refresh(
        payload.refresh_token,
        ip_address=ip,
        user_agent=ua,
    )
    db.commit()
    return ok(tokens.model_dump(), message="Token refreshed.")


@router.post("/logout", response_model=dict, status_code=status.HTTP_200_OK)
def logout(
    payload: LogoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Revoke the supplied refresh token. The access token will expire naturally."""
    AuthService(db).logout(payload.refresh_token, user_id=current_user.id)
    db.commit()
    return ok({}, message="Logged out successfully.")


@router.post("/logout-all", response_model=dict, status_code=status.HTTP_200_OK)
def logout_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Revoke all active refresh sessions for the authenticated user."""
    count = AuthService(db).logout_all(user_id=current_user.id)
    db.commit()
    return ok({"sessions_revoked": count}, message="All sessions revoked.")


@router.get("/me", response_model=dict, status_code=status.HTTP_200_OK)
def me(current_user: User = Depends(get_current_user)) -> dict:
    """Return the profile of the currently authenticated user."""
    return ok(UserOut.from_orm_user(current_user).model_dump())


@router.post("/users", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:create")),
) -> dict:
    """Create a new system user. Requires 'users:create' permission."""
    user = AuthService(db).create_user(payload, created_by=current_user.id)
    db.commit()
    return ok(UserOut.from_orm_user(user).model_dump(), message="User created.")
