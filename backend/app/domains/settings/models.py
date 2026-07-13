"""Settings domain model — runtime-configurable application parameters.

All values that would otherwise be hardcoded constants live here:
  - maximum_upload_size_mb
  - business_day_cutoff_time
  - inventory_reservation_timeout_hours
  - allowed_upload_extensions
  - plant_name / plant_code
  - notification_interval_minutes

The service layer provides typed accessors so callers never work with
raw strings directly.
"""

from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.base_model import AuditedModel


class Setting(AuditedModel):
    """A single runtime-configurable key-value application setting."""

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_settings_key"),
        UniqueConstraint("public_id", name="uq_settings_public_id"),
        Index("ix_settings_key", "key"),
    )

    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    value_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="string",
        comment="One of: string | integer | float | boolean | json",
    )
