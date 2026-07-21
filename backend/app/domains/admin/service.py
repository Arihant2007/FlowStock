"""Admin domain service — business logic for user and role administration.

Security rules:
  - Passwords are NEVER returned from get methods.
  - Password resets generate a cryptographically random temporary password,
    hash it immediately, set must_change_password=True, revoke all sessions,
    and return the plain temp password ONCE in the response.
  - Admins cannot view or modify existing password hashes.
  - All actions are written to the audit log.
"""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import DuplicateError, NotFoundError
from app.core.logger import get_logger
from app.domains.admin.repository import (
    AdminRoleRepository,
    AdminUserRepository,
    AdminWarehouseRepository,
)
from app.domains.admin.schemas import (
    CreateUserAdminRequest,
    ResetPasswordResponse,
    RoleOut,
    UpdateUserAdminRequest,
    UserAdminOut,
    UserListOut,
)
from app.domains.audit.service import AuditService
from app.domains.auth.models import Role, User
from app.domains.auth.repository import RefreshSessionRepository
from app.domains.auth.security import hash_password

logger = get_logger(__name__)


def _generate_temp_password() -> str:
    """Generate a cryptographically secure human-readable temporary password.

    Format: XXXX-XXXX-XXXX (uppercase alphanumeric, no ambiguous chars).
    Example: K3R7-MX9P-Q4ZN
    """
    # Remove visually ambiguous characters: O, 0, I, 1
    chars = "".join(
        c for c in (string.ascii_uppercase + string.digits) if c not in "OI01"
    )
    return "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(3))


def _user_to_list_out(user: User) -> UserListOut:
    """Map a User ORM instance to UserListOut."""
    return UserListOut(
        public_id=user.public_id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        role_name=user.role.name,
        role_public_id=user.role.public_id,
        warehouse_name=user.warehouse.name if user.warehouse else None,
        warehouse_public_id=user.warehouse.public_id if user.warehouse else None,
        is_active=user.is_active,
        is_locked=user.is_locked,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


def _user_to_admin_out(user: User) -> UserAdminOut:
    """Map a User ORM instance to UserAdminOut (full admin view)."""
    perms = [rp.permission.code for rp in user.role.permissions]
    return UserAdminOut(
        public_id=user.public_id,
        full_name=user.full_name,
        username=user.username,
        email=user.email,
        role_name=user.role.name,
        role_public_id=user.role.public_id,
        warehouse_name=user.warehouse.name if user.warehouse else None,
        warehouse_public_id=user.warehouse.public_id if user.warehouse else None,
        is_active=user.is_active,
        is_locked=user.is_locked,
        failed_login_count=user.failed_login_count,
        locked_until=user.locked_until,
        must_change_password=user.must_change_password,
        password_changed_at=user.password_changed_at,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        permissions=perms,
    )


class AdminService:
    """Business logic for the administration domain."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._user_repo = AdminUserRepository(db)
        self._role_repo = AdminRoleRepository(db)
        self._wh_repo = AdminWarehouseRepository(db)
        self._session_repo = RefreshSessionRepository(db)
        self._audit = AuditService(db)

    # ------------------------------------------------------------------
    # User listing & detail
    # ------------------------------------------------------------------

    def list_users(
        self,
        *,
        search: Optional[str] = None,
        role_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        is_active: Optional[bool] = None,
        is_locked: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[UserListOut], int]:
        """Return paginated user list with optional filters."""
        users, total = self._user_repo.list_users(
            search=search,
            role_id=role_id,
            warehouse_id=warehouse_id,
            is_active=is_active,
            is_locked=is_locked,
            page=page,
            page_size=page_size,
        )
        return [_user_to_list_out(u) for u in users], total

    def get_user(self, public_id) -> UserAdminOut:
        """Return full admin detail for a user.

        Raises:
            NotFoundError: If user not found.
        """
        user = self._user_repo.get_by_public_id(public_id)
        return _user_to_admin_out(user)

    def get_stats(self) -> dict:
        """Return KPI counts for the Users page header cards."""
        return {
            "total": self._user_repo.count_total(),
            "active": self._user_repo.count_active(),
            "locked": self._user_repo.count_locked(),
            "admins": self._user_repo.count_by_role_name("ADMIN"),
        }

    # ------------------------------------------------------------------
    # Create & Edit
    # ------------------------------------------------------------------

    def create_user(
        self, payload: CreateUserAdminRequest, *, admin_id: int
    ) -> tuple[UserAdminOut, str]:
        """Create a new user. Generates a temporary password and requires change.

        Raises:
            DuplicateError: Username or email already taken.
            NotFoundError:  Role or warehouse not found.
        """
        if self._user_repo.get_by_username(payload.username) is not None:
            raise DuplicateError(f"Username '{payload.username}' is already taken.")
        if payload.email and self._user_repo.get_by_email(str(payload.email)) is not None:
            raise DuplicateError(f"Email '{payload.email}' is already registered.")

        role = self._role_repo.get_by_public_id(payload.role_public_id)
        warehouse_id = None
        if payload.warehouse_public_id:
            wh = self._wh_repo.get_by_public_id(payload.warehouse_public_id)
            warehouse_id = wh.id

        temp_password = _generate_temp_password()

        new_user = User(
            username=payload.username,
            email=str(payload.email) if payload.email else None,
            full_name=payload.full_name,
            password_hash=hash_password(temp_password),
            password_changed_at=datetime.now(UTC),
            must_change_password=True,
            role_id=role.id,
            warehouse_id=warehouse_id,
            created_by=admin_id,
        )
        self._db.add(new_user)
        self._db.flush()

        self._audit.log_action(
            action="ADMIN_USER_CREATED",
            user_id=admin_id,
            resource_type="User",
            resource_id=new_user.id,
            details={"username": payload.username},
        )
        logger.info("admin_user_created", username=payload.username, admin_id=admin_id)

        # Re-fetch with all relations loaded
        user_out = _user_to_admin_out(self._user_repo.get_by_public_id(new_user.public_id))
        return user_out, temp_password

    def update_user(
        self,
        public_id,
        payload: UpdateUserAdminRequest,
        *,
        admin_id: int,
    ) -> UserAdminOut:
        """Edit user profile fields. Password is never in this payload.

        Raises:
            NotFoundError:  User, role, or warehouse not found.
            DuplicateError: New username or email already taken by another user.
        """
        user = self._user_repo.get_by_public_id(public_id)
        changes: dict = {}

        if payload.full_name is not None and payload.full_name != user.full_name:
            user.full_name = payload.full_name
            changes["full_name"] = payload.full_name

        if payload.is_active is not None and payload.is_active != user.is_active:
            user.is_active = payload.is_active
            changes["is_active"] = payload.is_active

        if payload.role_public_id is not None:
            role = self._role_repo.get_by_public_id(payload.role_public_id)
            if role.id != user.role_id:
                user.role_id = role.id
                changes["role"] = role.name

        if "warehouse_public_id" in payload.model_fields_set:
            if payload.warehouse_public_id is None:
                user.warehouse_id = None
                changes["warehouse"] = None
            else:
                wh = self._wh_repo.get_by_public_id(payload.warehouse_public_id)
                if wh.id != user.warehouse_id:
                    user.warehouse_id = wh.id
                    changes["warehouse"] = wh.name

        if changes:
            user.updated_by = admin_id
            user.version += 1
            self._db.flush()
            self._audit.log_action(
                action="ADMIN_USER_UPDATED",
                user_id=admin_id,
                resource_type="User",
                resource_id=user.id,
                details=changes,
            )

        return _user_to_admin_out(self._user_repo.get_by_public_id(user.public_id))

    # ------------------------------------------------------------------
    # Password Reset
    # ------------------------------------------------------------------

    def reset_password(self, public_id, *, admin_id: int) -> ResetPasswordResponse:
        """Generate a temporary password and reset the user's credentials.

        - Generates a cryptographically random temp password.
        - Hashes it immediately — plain text is never stored.
        - Sets must_change_password = True.
        - Sets password_changed_at = now.
        - Revokes all active sessions to force re-login.
        - Returns the plain temp password ONCE. It cannot be retrieved again.
        """
        user = self._user_repo.get_by_public_id(public_id)
        temp_password = _generate_temp_password()

        user.password_hash = hash_password(temp_password)
        user.must_change_password = True
        user.password_changed_at = datetime.now(UTC)
        user.version += 1
        user.updated_by = admin_id
        self._db.flush()

        # Revoke all active sessions — user must log in fresh with temp password.
        self._session_repo.revoke_all_for_user(user.id)

        self._audit.log_action(
            action="ADMIN_PASSWORD_RESET",
            user_id=admin_id,
            resource_type="User",
            resource_id=user.id,
            details={"username": user.username},
        )
        logger.info(
            "admin_password_reset",
            target_user_id=user.id,
            admin_id=admin_id,
        )

        return ResetPasswordResponse(temporary_password=temp_password)

    # ------------------------------------------------------------------
    # Activate / Deactivate
    # ------------------------------------------------------------------

    def activate_user(self, public_id, *, admin_id: int) -> UserAdminOut:
        """Activate a deactivated user."""
        user = self._user_repo.get_by_public_id(public_id)
        user.is_active = True
        user.updated_by = admin_id
        user.version += 1
        self._db.flush()

        self._audit.log_action(
            action="ADMIN_USER_ACTIVATED",
            user_id=admin_id,
            resource_type="User",
            resource_id=user.id,
            details={"username": user.username},
        )
        return _user_to_admin_out(self._user_repo.get_by_public_id(user.public_id))

    def deactivate_user(self, public_id, *, admin_id: int) -> UserAdminOut:
        """Deactivate a user and revoke all their active sessions."""
        user = self._user_repo.get_by_public_id(public_id)
        user.is_active = False
        user.updated_by = admin_id
        user.version += 1
        self._db.flush()

        self._session_repo.revoke_all_for_user(user.id)

        self._audit.log_action(
            action="ADMIN_USER_DEACTIVATED",
            user_id=admin_id,
            resource_type="User",
            resource_id=user.id,
            details={"username": user.username},
        )
        return _user_to_admin_out(self._user_repo.get_by_public_id(user.public_id))

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------

    def list_roles(self) -> list[RoleOut]:
        """Return all active roles (for dropdowns)."""
        roles = self._role_repo.list_all()
        return [RoleOut(public_id=r.public_id, name=r.name) for r in roles]
