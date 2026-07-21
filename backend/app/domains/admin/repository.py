"""Admin domain repository — data access for user administration."""

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.domains.auth.models import Role, RolePermission, User
from app.domains.master.models import Warehouse


def _user_admin_stmt():
    """Base User select with role, permissions, and warehouse eager-loaded."""
    return (
        select(User)
        .where(User.deleted_at.is_(None))
        .options(
            selectinload(User.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission),
            selectinload(User.warehouse),
        )
    )


class AdminUserRepository:
    """Data access methods for admin-level user operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_public_id(self, public_id) -> User:
        """Return User by public_id with all relations loaded.

        Raises:
            NotFoundError: If user not found.
        """
        user = self.db.scalar(
            _user_admin_stmt().where(User.public_id == public_id)
        )
        if user is None:
            raise NotFoundError(f"User '{public_id}' not found.")
        return user

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.scalar(
            _user_admin_stmt().where(User.username == username)
        )

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(
            _user_admin_stmt().where(User.email == email)
        )

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
    ) -> tuple[list[User], int]:
        """Return (users, total_count) with optional filters."""
        stmt = _user_admin_stmt().order_by(User.full_name)

        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).like(term),
                    func.lower(User.username).like(term),
                    func.lower(User.email).like(term),
                )
            )
        if role_id is not None:
            stmt = stmt.where(User.role_id == role_id)
        if warehouse_id is not None:
            stmt = stmt.where(User.warehouse_id == warehouse_id)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if is_locked is not None:
            stmt = stmt.where(User.is_locked == is_locked)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.scalar(count_stmt) or 0

        offset = (page - 1) * page_size
        users = list(self.db.scalars(stmt.offset(offset).limit(page_size)).all())
        return users, total

    def count_by_role_name(self, role_name: str) -> int:
        """Count users with a given role name."""
        return (
            self.db.scalar(
                select(func.count(User.id))
                .join(Role, User.role_id == Role.id)
                .where(User.deleted_at.is_(None))
                .where(Role.name == role_name)
            )
            or 0
        )

    def count_active(self) -> int:
        return self.db.scalar(
            select(func.count(User.id))
            .where(User.deleted_at.is_(None))
            .where(User.is_active.is_(True))
        ) or 0

    def count_locked(self) -> int:
        return self.db.scalar(
            select(func.count(User.id))
            .where(User.deleted_at.is_(None))
            .where(User.is_locked.is_(True))
        ) or 0

    def count_total(self) -> int:
        return self.db.scalar(
            select(func.count(User.id)).where(User.deleted_at.is_(None))
        ) or 0


class AdminRoleRepository:
    """Data access for roles (admin domain)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_all(self) -> list[Role]:
        return list(
            self.db.scalars(
                select(Role).where(Role.deleted_at.is_(None)).order_by(Role.name)
            ).all()
        )

    def get_by_public_id(self, public_id) -> Role:
        role = self.db.scalar(
            select(Role)
            .where(Role.public_id == public_id)
            .where(Role.deleted_at.is_(None))
        )
        if role is None:
            raise NotFoundError(f"Role '{public_id}' not found.")
        return role


class AdminWarehouseRepository:
    """Data access for warehouses (used in admin create/edit)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_public_id(self, public_id) -> Warehouse:
        wh = self.db.scalar(
            select(Warehouse)
            .where(Warehouse.public_id == public_id)
            .where(Warehouse.deleted_at.is_(None))
        )
        if wh is None:
            raise NotFoundError(f"Warehouse '{public_id}' not found.")
        return wh
