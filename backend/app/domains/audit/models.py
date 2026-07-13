"""Audit domain models: AuditLog (user actions) and BusinessEventLog (domain events).

JSONB note:
  PostgreSQL uses JSONB for indexed JSON queries.
  SQLite (used in tests) uses JSON via with_variant().
  The application always targets PostgreSQL in production.
"""

from sqlalchemy import JSON, BigInteger, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.base_model import BaseModel

# Dialect-aware JSON column: JSONB on Postgres, JSON on SQLite/others.
_JsonColumn = JSONB().with_variant(JSON(), "sqlite")


class AuditLog(BaseModel):
    """Records every significant user-initiated action in the system.

    Append-only. Never updated or deleted.

    Tracked actions include:
      LOGIN_SUCCESS, LOGIN_FAILED, LOGIN_BLOCKED_LOCKED, LOGOUT, LOGOUT_ALL,
      USER_CREATED, USER_UPDATED, PASSWORD_CHANGED,
      REQUEST_SUBMITTED, REQUEST_APPROVED, REQUEST_REJECTED,
      INVENTORY_UPLOAD, EXCEL_COMMITTED,
      REPORT_EXPORTED, SETTING_UPDATED
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict] = mapped_column(_JsonColumn, nullable=False, default=dict)


class BusinessEventLog(BaseModel):
    """Records domain-level business events for process troubleshooting.

    Distinct from AuditLog (security/compliance), this table records
    what the system accomplished in business terms:
      MATERIAL_REQUESTED, INVENTORY_RESERVED, INVENTORY_TRANSFERRED,
      ODS_UPDATED, CLOSING_INVENTORY_SUBMITTED, REPORT_GENERATED,
      EOD_RECONCILIATION_COMPLETE, OPENING_BALANCE_INGESTED

    NOT an event bus — purely an append-only audit trail.
    """

    __tablename__ = "business_event_logs"
    __table_args__ = (
        Index("ix_biz_event_logs_event_type", "event_type"),
        Index("ix_biz_event_logs_created_at", "created_at"),
        Index("ix_biz_event_logs_reference", "reference_type", "reference_id"),
    )

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict] = mapped_column(_JsonColumn, nullable=False, default=dict)
    triggered_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
