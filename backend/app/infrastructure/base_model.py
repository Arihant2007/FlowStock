"""Declarative base model with shared audit columns.

Every domain model inherits from one of two base classes:

  BaseModel  — for append-only ledger tables (no soft-delete, no version).
  AuditedModel — for editable master/operational tables that need:
      - public_id (UUID for external API exposure)
      - version   (optimistic locking)
      - created_at / updated_at
      - created_by / updated_by  (FK to users.id)
      - deleted_at / deleted_by  (soft delete)
"""

import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base shared by all domain models."""


class BaseModel(Base):
    """Minimal append-only base — used by ledger tables.

    Contains only `id` (surrogate PK) and `created_at`.
    These tables are never updated or soft-deleted.
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AuditedModel(BaseModel):
    """Full-featured base for editable master and operational tables.

    Adds:
      - public_id   : UUID exposed on external APIs; never the internal id.
      - version     : Optimistic locking counter, starts at 1.
      - updated_at  : Auto-updated on every write.
      - created_by  : FK to users.id — set by the service layer.
      - updated_by  : FK to users.id — set by the service layer.
      - deleted_at  : Non-null signals a soft delete.
      - deleted_by  : FK to users.id — set by the service layer.
    """

    __abstract__ = True

    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft-deleted."""
        return self.deleted_at is not None
