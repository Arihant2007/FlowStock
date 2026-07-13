"""Audit service — records user actions and business events.

Called by service layers (AuthService, RequestService, InventoryService)
after successful operations. Never raises exceptions — audit failures
are logged but do not roll back business transactions.
"""

from sqlalchemy.orm import Session

from app.core.logger import get_logger
from app.domains.audit.models import AuditLog, BusinessEventLog

logger = get_logger(__name__)


class AuditService:
    """Records user-initiated actions and business domain events."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def log_action(
        self,
        *,
        action: str,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: int | None = None,
        ip_address: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Append a user action to the audit log.

        This method must never raise. If insertion fails, log the error
        and continue — business transactions must not be rolled back due
        to audit failures.
        """
        try:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                details=details or {},
            )
            self._db.add(entry)
            self._db.flush()
        except Exception as exc:  # noqa: BLE001
            logger.error("audit_log_failed", action=action, exc_info=exc)

    def log_event(
        self,
        *,
        event_type: str,
        reference_type: str | None = None,
        reference_id: int | None = None,
        payload: dict | None = None,
        triggered_by: int | None = None,
    ) -> None:
        """Append a business domain event to the business event log."""
        try:
            entry = BusinessEventLog(
                event_type=event_type,
                reference_type=reference_type,
                reference_id=reference_id,
                payload=payload or {},
                triggered_by=triggered_by,
            )
            self._db.add(entry)
            self._db.flush()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "business_event_log_failed", event_type=event_type, exc_info=exc
            )
