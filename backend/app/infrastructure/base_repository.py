"""Generic repository base providing standard CRUD with optimistic locking.

Every domain repository extends BaseRepository[ModelT] and immediately
inherits safe get, list, create, update (with version check), and soft-delete
operations. Domain-specific queries are added in the domain repository.

Design decisions:
  - All mutating operations require a `Session` passed by the caller, so
    the service layer owns the transaction boundary.
  - `update` raises OptimisticLockError when the supplied version does not
    match the current database version, preventing lost updates.
  - `soft_delete` never physically removes rows from master tables.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, OptimisticLockError
from app.infrastructure.base_model import AuditedModel

ModelT = TypeVar("ModelT", bound=AuditedModel)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository for AuditedModel subclasses."""

    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, record_id: int) -> ModelT:
        """Fetch a non-deleted record by surrogate PK or raise NotFoundError."""
        stmt = (
            select(self.model)
            .where(self.model.id == record_id)
            .where(self.model.deleted_at.is_(None))
        )
        obj = self.db.scalar(stmt)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} with id={record_id} not found.")
        return obj

    def get_by_public_id(self, public_id: str | uuid.UUID) -> ModelT:
        """Fetch a non-deleted record by UUID public_id or raise NotFoundError."""
        if isinstance(public_id, str):
            public_id = uuid.UUID(public_id)

        stmt = (
            select(self.model)
            .where(self.model.public_id == public_id)
            .where(self.model.deleted_at.is_(None))
        )
        obj = self.db.scalar(stmt)
        if obj is None:
            raise NotFoundError(
                f"{self.model.__name__} with public_id={public_id} not found."
            )
        return obj

    def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelT], int]:
        """Return a paginated list of non-deleted records and the total count."""
        base_stmt = select(self.model).where(self.model.deleted_at.is_(None))
        from sqlalchemy import func

        total: int = (
            self.db.scalar(
                select(func.count(self.model.id)).where(self.model.deleted_at.is_(None))
            )
            or 0
        )
        rows = self.db.scalars(
            base_stmt.offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(rows), total

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, obj: ModelT) -> ModelT:
        """Persist a new record and flush to populate server-side defaults."""
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def update(
        self,
        obj: ModelT,
        updates: dict[str, Any],
        *,
        updated_by: int,
    ) -> ModelT:
        """Apply updates using optimistic locking.

        Raises OptimisticLockError if `obj.version` has changed since it
        was last loaded, preventing silent overwrites from concurrent requests.
        """
        current_version = self.db.scalar(
            select(self.model.version).where(self.model.id == obj.id)
        )
        if current_version != obj.version:
            raise OptimisticLockError()

        for key, value in updates.items():
            setattr(obj, key, value)

        obj.version = obj.version + 1
        obj.updated_by = updated_by
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: ModelT, *, deleted_by: int) -> None:
        """Mark a record as deleted without physically removing it."""
        obj.deleted_at = datetime.now(UTC)
        obj.deleted_by = deleted_by
        self.db.flush()
