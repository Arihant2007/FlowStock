"""Requests domain models: MaterialRequest, MaterialRequestSKU, MaterialRequestItem.

Structure:
    MaterialRequest (one per morning submission)
        └── MaterialRequestSKU (one per SKU planned that day)
                └── MaterialRequestItem (one per RM/PM required)

This three-level hierarchy allows a single morning request to contain
multiple SKUs, each with their own material requirements.

Status state machine:
    SUBMITTED -> RESERVED -> APPROVED -> DISPATCHED -> RECEIVED -> CLOSED
                          -> PARTIALLY_APPROVED -> DISPATCHED -> ...
                -> REJECTED (terminal)

    Note: DRAFT state removed per V1 business logic. New requests are
    immediately placed in SUBMITTED status.
"""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.base_model import AuditedModel

if TYPE_CHECKING:
    from app.domains.master.models import SKU, Material

REQUEST_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "PARTIALLY_APPROVED",
    "DISPATCHED",
    "RECEIVED",
    "CLOSED",
    "REJECTED",
)
STATUS_CHECK = f"status IN ({', '.join(repr(s) for s in REQUEST_STATUSES)})"


class MaterialRequest(AuditedModel):
    """The top-level morning material request submitted by an ODS operator."""

    __tablename__ = "material_requests"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_material_requests_public_id"),
        CheckConstraint(STATUS_CHECK, name="ck_material_requests_status"),
        Index("ix_material_requests_status_date", "status", "created_at"),
    )

    request_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_number: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    ods_warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    rmpm_warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True
    )

    skus: Mapped[list["MaterialRequestSKU"]] = relationship(
        "MaterialRequestSKU", back_populates="request", cascade="all, delete-orphan"
    )
    history: Mapped[list["MaterialRequestHistory"]] = relationship(
        "MaterialRequestHistory", back_populates="request", cascade="all, delete-orphan"
    )

class MaterialRequestHistory(AuditedModel):
    """Audit log of status transitions and review actions for a request."""

    __tablename__ = "material_request_history"
    __table_args__ = (
        Index("ix_mat_req_history_req_id", "request_id"),
    )

    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    review_comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped["MaterialRequest"] = relationship("MaterialRequest", back_populates="history")


class MaterialRequestSKU(AuditedModel):
    """One SKU line within a MaterialRequest."""

    __tablename__ = "material_request_skus"
    __table_args__ = (
        CheckConstraint(
            "planned_production_qty > 0",
            name="ck_material_request_skus_qty_pos",
        ),
        Index("ix_mat_req_sku_request_id", "request_id"),
        Index("ix_mat_req_sku_sku_id", "sku_id"),
    )

    request_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False
    )
    planned_production_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    bom_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("bom_versions.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Snapshot of the BOM version used at request time.",
    )

    request: Mapped["MaterialRequest"] = relationship(
        "MaterialRequest", back_populates="skus"
    )
    items: Mapped[list["MaterialRequestItem"]] = relationship(
        "MaterialRequestItem",
        back_populates="request_sku",
        cascade="all, delete-orphan",
    )
    sku: Mapped["SKU"] = relationship("SKU")


class MaterialRequestItem(AuditedModel):
    """A single material requirement line within a MaterialRequestSKU."""

    __tablename__ = "material_request_items"
    __table_args__ = (
        CheckConstraint("requested_qty >= 0", name="ck_mat_req_item_req_qty_pos"),
        CheckConstraint(
            "approved_qty IS NULL OR approved_qty >= 0",
            name="ck_mat_req_item_appr_qty_non_neg",
        ),
        CheckConstraint(
            "remaining_from_previous_day >= 0",
            name="ck_mat_req_item_remaining_non_neg",
        ),
        Index("ix_mat_req_items_request_sku_id", "request_sku_id"),
        Index("ix_mat_req_items_material_id", "material_id"),
    )

    request_sku_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_request_skus.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    gross_required_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        comment="= BOM quantity × planned_production_qty",
    )
    remaining_from_previous_day: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
        comment="Physically counted leftover from the previous day.",
    )
    requested_qty: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        comment="= gross_required_qty - remaining_from_previous_day",
    )
    approved_qty: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        nullable=True,
        comment="Set by RMPM operator during approval. NULL = not yet approved.",
    )
    dispatched_qty: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True, comment="Set by RMPM operator during dispatch."
    )
    received_qty: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True, comment="Set by ODS operator during receive."
    )

    request_sku: Mapped["MaterialRequestSKU"] = relationship(
        "MaterialRequestSKU", back_populates="items"
    )
    material: Mapped["Material"] = relationship("Material")

    @property
    def material_public_id(self):
        return self.material.public_id if self.material else None

    @property
    def material_name(self):
        return self.material.name if self.material else None

    @property
    def material_code(self):
        return self.material.code if self.material else None

    @property
    def material_type(self):
        return self.material.material_type.name if self.material and self.material.material_type else "RM"
