"""Auth domain dependencies — FastAPI dependency injection for auth/RBAC.

Usage in routes:
    current_user: User = Depends(get_current_user)
    _: User = Depends(require_permission("inventory:approve"))
"""

from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.errors import (
    AuthenticationError,
    PermissionDeniedError,
)
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import decode_token
from app.infrastructure.database import get_db

# This tells FastAPI where to find the Bearer token and enables
# the Authorize button in Swagger UI.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from a Bearer JWT access token.

    Raises:
        AuthenticationError:  Token invalid, expired, or wrong type.
        TokenRevokedError:    Token was issued but later revoked.
    """
    payload = decode_token(token)

    if payload.get("token_type") != "access":
        raise AuthenticationError("Supplied token is not an access token.")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token is missing subject claim.")

    try:
        user_id = int(user_id_str)
    except ValueError as exc:
        raise AuthenticationError("Token subject is malformed.") from exc

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)

    if not user.is_active:
        raise AuthenticationError("User account is deactivated.")

    return user


def require_permission(permission_code: str) -> Callable[..., User]:
    """Return a FastAPI dependency that enforces the given permission code.

    Usage:
        @router.get("/sensitive", dependencies=[Depends(require_permission("reports:read"))])

    Raises:
        PermissionDeniedError: If the current user's role does not include the permission.
    """

    def check(current_user: User = Depends(get_current_user)) -> User:
        codes = {rp.permission.code for rp in current_user.role.permissions}
        if permission_code not in codes:
            raise PermissionDeniedError(
                f"Permission '{permission_code}' is required for this action.",
                details={"required": permission_code, "role": current_user.role.name},
            )
        return current_user

    return check
