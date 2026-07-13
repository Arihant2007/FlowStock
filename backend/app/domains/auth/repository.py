"""Auth domain repository — data access layer for User, Role, Permission, RefreshSession."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.domains.auth.models import (
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
)
from app.infrastructure.base_repository import BaseRepository


def _user_with_role_stmt() -> object:
    """Return base User select statement with eager-loaded role and permissions."""
    return (
        select(User)
        .where(User.deleted_at.is_(None))
        .options(
            selectinload(User.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission)
        )
    )


class UserRepository(BaseRepository[User]):
    """Data access methods for the User entity."""

    model = User

    def get_by_id(self, user_id: int) -> User:
        """Load user with role and permissions eagerly (avoids N+1 queries)."""
        user = self.db.scalar(
            _user_with_role_stmt().where(User.id == user_id)  # type: ignore[attr-defined]
        )
        if user is None:
            raise NotFoundError(f"User with id={user_id} not found.")
        return user

    def get_by_username(self, username: str) -> User | None:
        """Return User by username or None if not found."""
        return self.db.scalar(
            _user_with_role_stmt().where(User.username == username)  # type: ignore[attr-defined]
        )

    def get_by_email(self, email: str) -> User | None:
        """Return User by email address or None if not found."""
        return self.db.scalar(
            _user_with_role_stmt().where(User.email == email)  # type: ignore[attr-defined]
        )

    def get_by_username_or_email(self, identifier: str) -> User | None:
        """Return User matching either username or email. Supports login with both."""
        return self.db.scalar(
            _user_with_role_stmt().where(  # type: ignore[attr-defined]
                (User.username == identifier) | (User.email == identifier)
            )
        )


class RoleRepository(BaseRepository[Role]):
    """Data access methods for the Role entity."""

    model = Role

    def get_by_name(self, name: str) -> Role | None:
        """Return Role by name or None."""
        return self.db.scalar(
            select(Role).where(Role.name == name).where(Role.deleted_at.is_(None))
        )


class PermissionRepository(BaseRepository[Permission]):
    """Data access methods for the Permission entity."""

    model = Permission

    def get_by_code(self, code: str) -> Permission | None:
        """Return Permission by code or None."""
        return self.db.scalar(
            select(Permission)
            .where(Permission.code == code)
            .where(Permission.deleted_at.is_(None))
        )


class RefreshSessionRepository:
    """Data access methods for RefreshSession (refresh token revocation store)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        jti: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshSession:
        """Persist a new active refresh session record."""
        session = RefreshSession(
            user_id=user_id,
            jti=jti,
            expires_at=expires_at,
            revoked=False,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def get_by_jti(self, jti: str) -> RefreshSession | None:
        """Return the RefreshSession for the given jti or None."""
        return self.db.scalar(select(RefreshSession).where(RefreshSession.jti == jti))

    def revoke(self, jti: str) -> bool:
        """Mark a refresh session as revoked. Returns True if found and revoked."""
        session = self.get_by_jti(jti)
        if session is None:
            return False
        session.revoked = True
        self.db.flush()
        return True

    def revoke_all_for_user(self, user_id: int) -> int:
        """Revoke all active sessions for a user (e.g., forced logout on password change).

        Returns the number of sessions revoked.
        """
        sessions = self.db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked.is_(False),
                RefreshSession.expires_at > datetime.now(UTC),
            )
        ).all()
        for s in sessions:
            s.revoked = True
        self.db.flush()
        return len(sessions)
