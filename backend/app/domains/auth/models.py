"""Auth domain models: User, Role, Permission, RolePermission, RefreshSession, LoginAttempt."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.base_model import AuditedModel, BaseModel


class Permission(AuditedModel):
    """A single named permission that can be granted to roles.

    Examples: "inventory:approve", "requests:create", "reports:export"
    """

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
        UniqueConstraint("public_id", name="uq_permissions_public_id"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    roles: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="permission"
    )


class Role(AuditedModel):
    """A named collection of permissions assigned to users."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("name", name="uq_roles_name"),
        UniqueConstraint("public_id", name="uq_roles_public_id"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission", back_populates="role"
    )
    users: Mapped[list["User"]] = relationship("User", back_populates="role")


class RolePermission(AuditedModel):
    """Join table linking roles to their allowed permissions."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions_role_perm"
        ),
    )

    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped["Role"] = relationship("Role", back_populates="permissions")
    permission: Mapped["Permission"] = relationship(
        "Permission", back_populates="roles"
    )


class User(AuditedModel):
    """System user with role-based access control.

    Additional security columns:
      - failed_login_count: Incremented on each failed login attempt. Reset on success.
      - locked_until:       When non-null, account is locked until this UTC timestamp.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("public_id", name="uq_users_public_id"),
        Index("ix_users_role_id", "role_id"),
    )

    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True,
        comment="Primary warehouse assignment for inventory operations."
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Consecutive failed login attempts since last successful login.",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account locked until this UTC time. NULL = not locked.",
    )

    role: Mapped["Role"] = relationship("Role", back_populates="users")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    refresh_sessions: Mapped[list["RefreshSession"]] = relationship(
        "RefreshSession", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshSession(BaseModel):
    """A server-side record tracking an issued refresh token.

    Refresh tokens are revocable by deleting or revoking the RefreshSession.
    This prevents stateless refresh-token abuse after logout.

    jti (JWT ID) is stored here and must be present and active in this table
    for any refresh attempt to succeed.
    """

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        UniqueConstraint("jti", name="uq_refresh_sessions_jti"),
        Index("ix_refresh_sessions_user_id", "user_id"),
        Index("ix_refresh_sessions_jti", "jti"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        comment="JWT ID claim from the refresh token (UUID).",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this session was explicitly revoked (logout).",
    )
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="refresh_sessions")
