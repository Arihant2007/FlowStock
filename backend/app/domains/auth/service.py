"""Auth domain service — business logic for authentication and user management.

Security model:
  - Login accepts username OR email.
  - Failed attempts are counted; account is locked for LOCKOUT_DURATION_MINUTES
    after MAX_FAILED_ATTEMPTS consecutive failures.
  - Successful login resets failed_login_count.
  - Refresh tokens are revocable: every issuance creates a RefreshSession row
    keyed by jti. Logout revokes the session; refresh verifies the jti is active.
  - All auth events (success, failure, logout) are written to the audit log.
"""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    AccountLockedError,
    AuthenticationError,
    DuplicateError,
    NotFoundError,
    TokenRevokedError,
)
from app.core.logger import get_logger
from app.domains.audit.service import AuditService
from app.domains.auth.models import User
from app.domains.auth.repository import (
    RefreshSessionRepository,
    RoleRepository,
    UserRepository,
)
from app.domains.auth.schemas import ChangePasswordRequest, CreateUserRequest, TokenResponse
from app.domains.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

settings = get_settings()
logger = get_logger(__name__)

# Account lockout configuration (can be moved to Settings domain in future).
MAX_FAILED_ATTEMPTS: int = 5
LOCKOUT_DURATION_MINUTES: int = 15


def _get_permission_codes(user: User) -> list[str]:
    """Extract flat list of permission codes from a user's loaded role."""
    return [rp.permission.code for rp in user.role.permissions]


class AuthService:
    """Handles all authentication and user management business logic."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._user_repo = UserRepository(db)
        self._role_repo = RoleRepository(db)
        self._session_repo = RefreshSessionRepository(db)
        self._audit = AuditService(db)

    def login(
        self,
        identifier: str,
        password: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Authenticate using username OR email, return tokens.

        Raises:
            AccountLockedError:   If the account is temporarily locked.
            AuthenticationError:  If credentials are invalid or account is inactive.
        """
        user = self._user_repo.get_by_username_or_email(identifier)

        # Check lockout BEFORE verifying password to avoid timing-based enumeration.
        if user is not None and user.locked_until is not None:
            now = datetime.now(UTC)
            lock_expires = user.locked_until
            # Make naive datetimes timezone-aware if necessary (SQLite compat).
            if lock_expires.tzinfo is None:
                lock_expires = lock_expires.replace(tzinfo=UTC)
            if now < lock_expires:
                minutes_left = math.ceil((lock_expires - now).total_seconds() / 60)
                self._audit.log_action(
                    action="LOGIN_BLOCKED_LOCKED",
                    user_id=user.id,
                    ip_address=ip_address,
                    details={"identifier": identifier},
                )
                raise AccountLockedError(minutes_remaining=minutes_left)

        # Check admin-imposed lock (is_locked flag — separate from auto-lockout).
        if user is not None and user.is_locked:
            self._audit.log_action(
                action="LOGIN_BLOCKED_ADMIN_LOCK",
                user_id=user.id,
                ip_address=ip_address,
                details={"identifier": identifier},
            )
            raise AccountLockedError(minutes_remaining=0)

        # Constant-time check: always call verify even if user not found to prevent
        # timing attacks that reveal whether a username/email exists.
        password_valid = (
            verify_password(password, user.password_hash) if user is not None else False
        )

        if user is None or not password_valid:
            if user is not None:
                self._record_failed_attempt(user)
            self._audit.log_action(
                action="LOGIN_FAILED",
                user_id=user.id if user else None,
                ip_address=ip_address,
                details={"identifier": identifier},
            )
            logger.warning("auth_failed", identifier=identifier)
            raise AuthenticationError("Invalid credentials.")

        if not user.is_active:
            raise AuthenticationError("User account is deactivated.")

        # Success — reset lockout counters.
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(UTC)
        user.version += 1

        permissions = _get_permission_codes(user)

        access_token = create_access_token(
            subject=str(user.id),
            public_id=str(user.public_id),
            role=user.role.name,
            permissions=permissions,
        )
        refresh_token, jti = create_refresh_token(
            subject=str(user.id),
            public_id=str(user.public_id),
        )

        expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        self._session_repo.create(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self._audit.log_action(
            action="LOGIN_SUCCESS",
            user_id=user.id,
            ip_address=ip_address,
            details={"role": user.role.name},
        )
        logger.info("auth_success", user_id=user.id, identifier=identifier)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            permissions=permissions,
        )

    def refresh(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Validate a refresh token and issue a new access + refresh token pair.

        Raises:
            AuthenticationError: Token invalid or expired.
            TokenRevokedError:   Token was revoked (user logged out).
        """
        payload = decode_token(refresh_token)

        if payload.get("token_type") != "refresh":
            raise AuthenticationError("Supplied token is not a refresh token.")

        jti = payload.get("jti")
        if not jti:
            raise AuthenticationError("Refresh token is missing jti claim.")

        db_session = self._session_repo.get_by_jti(jti)
        if db_session is None or db_session.revoked:
            raise TokenRevokedError(
                "Refresh token has been revoked. Please log in again."
            )

        now = datetime.now(UTC)
        expires = db_session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if now >= expires:
            raise AuthenticationError("Refresh token has expired.")

        user = self._user_repo.get_by_id(int(payload["sub"]))
        if not user.is_active:
            raise AuthenticationError("User account is deactivated.")

        # Rotate: revoke the old session and issue a new one.
        self._session_repo.revoke(jti)

        permissions = _get_permission_codes(user)
        access_token = create_access_token(
            subject=str(user.id),
            public_id=str(user.public_id),
            role=user.role.name,
            permissions=permissions,
        )
        new_refresh_token, new_jti = create_refresh_token(
            subject=str(user.id),
            public_id=str(user.public_id),
        )
        new_expires_at = datetime.now(UTC) + timedelta(
            days=settings.refresh_token_expire_days
        )
        self._session_repo.create(
            user_id=user.id,
            jti=new_jti,
            expires_at=new_expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            permissions=permissions,
        )

    def logout(self, refresh_token: str, *, user_id: int) -> None:
        """Revoke the supplied refresh token. If invalid, silently succeeds.

        This is intentionally forgiving — a client that has already lost the
        token shouldn't get a different response.
        """
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                self._session_repo.revoke(jti)
        except AuthenticationError:
            pass  # Expired/invalid token — nothing to revoke.

        self._audit.log_action(action="LOGOUT", user_id=user_id)
        logger.info("user_logged_out", user_id=user_id)

    def logout_all(self, *, user_id: int) -> int:
        """Revoke ALL active refresh sessions for a user (forced logout everywhere)."""
        count = self._session_repo.revoke_all_for_user(user_id)
        self._audit.log_action(
            action="LOGOUT_ALL",
            user_id=user_id,
            details={"sessions_revoked": count},
        )
        return count

    def create_user(self, payload: CreateUserRequest, *, created_by: int) -> User:
        """Create a new system user (admin operation).

        Raises:
            DuplicateError:  Username or email already taken.
            NotFoundError:   Role not found.
        """
        if self._user_repo.get_by_username(payload.username) is not None:
            raise DuplicateError(f"Username '{payload.username}' is already taken.")

        if self._user_repo.get_by_email(str(payload.email)) is not None:
            raise DuplicateError(f"Email '{payload.email}' is already registered.")

        try:
            role = self._role_repo.get_by_public_id(payload.role_public_id)
        except NotFoundError as e:
            raise NotFoundError(f"Role '{payload.role_public_id}' not found.") from e

        new_user = User(
            username=payload.username,
            email=str(payload.email),
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            password_changed_at=datetime.now(UTC),
            role_id=role.id,
            created_by=created_by,
        )
        self._user_repo.create(new_user)
        self._audit.log_action(
            action="USER_CREATED",
            user_id=created_by,
            resource_type="User",
            details={"username": payload.username},
        )
        logger.info("user_created", username=payload.username, created_by=created_by)
        return new_user

    def change_own_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        """Allow a user to change their own password.

        Raises:
            AuthenticationError: If current_password is incorrect.
        """
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect.")

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.must_change_password = False
        user.version += 1

        # Revoke all other active sessions to force re-login everywhere else.
        self._session_repo.revoke_all_for_user(user.id)

        self._audit.log_action(
            action="PASSWORD_CHANGED_SELF",
            user_id=user.id,
            details={},
        )
        logger.info("password_changed_self", user_id=user.id)

    def update_own_profile(
        self,
        user: User,
        payload,
    ) -> User:
        """Allow a user to update their own profile (username, full_name)."""
        changed = False

        if payload.username and payload.username.strip() != user.username:
            new_username = payload.username.strip()
            if new_username.lower() in ["admin", "system", "root"]:
                from app.core.errors import ValidationError
                raise ValidationError("Reserved username cannot be used.")
            
            existing = self._user_repo.get_by_username(new_username)
            if existing is not None and existing.id != user.id:
                from app.core.errors import DuplicateError
                raise DuplicateError(f"Username '{new_username}' is already taken.")
            user.username = new_username
            changed = True

        if payload.full_name and payload.full_name.strip() != user.full_name:
            user.full_name = payload.full_name.strip()
            changed = True

        if changed:
            user.version += 1
            self._audit.log_action(
                action="profile_updated",
                user_id=user.id,
                details={"username": user.username, "full_name": user.full_name},
            )
            logger.info("profile_updated", user_id=user.id, username=user.username)

        return user

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_failed_attempt(self, user: User) -> None:
        """Increment failed counter and lock account if threshold exceeded."""
        user.failed_login_count += 1
        user.version += 1
        if user.failed_login_count >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            logger.warning(
                "account_locked",
                user_id=user.id,
                duration_minutes=LOCKOUT_DURATION_MINUTES,
            )
        self._db.flush()
