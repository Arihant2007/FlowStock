"""Inventory domain models: InventoryTransaction, InventoryReservation,
InventorySnapshot.

Design notes:
  - InventoryTransaction is append-only (inherits BaseModel, not AuditedModel).
    Records are never updated or deleted.
  - All quantities use NUMERIC(18,4) to prevent floating-point errors.
  - source_warehouse_id and destination_warehouse_id allow any combination
    of warehouses, making the model future-proof for multi-warehouse plants.
  - quantity is always POSITIVE. The transaction_type communicates direction.
"""

from decimal import Decimal

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
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.base_model import AuditedModel, BaseModel


class InventoryTransaction(BaseModel):
    """Immutable ledger entry recording every inventory movement.

    The current balance for any (material, warehouse) pair is always
    derived by summing the relevant InventoryTransaction records. This
    guarantees a complete, auditable history.

    transaction_type values:
      RECEIPT        — Material received into a warehouse (no source).
      DISPATCH       — Material dispatched from a warehouse (no destination).
      ADJUSTMENT     — Balance correction from EOD physical count.
      TRANSFER_OUT   — Paired with TRANSFER_IN: the deduction side of a transfer.
      TRANSFER_IN    — Paired with TRANSFER_OUT: the addition side.
      RESERVATION    — Soft-hold placed during request approval pipeline.
      RESERVATION_RELEASE — Reversal of a RESERVATION on rejection.
      CONSUMPTION    — Material consumed in production.
    """

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inv_tx_qty_positive"),
        CheckConstraint(
            "transaction_type IN ("
            "'RECEIPT','DISPATCH','ADJUSTMENT','TRANSFER_OUT','TRANSFER_IN',"
            "'RESERVATION','RESERVATION_RELEASE','CONSUMPTION'"
            ")",
            name="ck_inv_tx_type",
        ),
        Index("ix_inv_tx_material_warehouse", "material_id", "source_warehouse_id"),
        Index("ix_inv_tx_destination", "destination_warehouse_id"),
        Index("ix_inv_tx_created_at", "created_at"),
        Index("ix_inv_tx_reference", "reference_type", "reference_id"),
    )

    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    source_warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL for pure RECEIPT transactions.",
    )
    destination_warehouse_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL for pure DISPATCH transactions.",
    )
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="E.g., 'MATERIAL_REQUEST', 'EOD_COUNT', 'OPENING_BALANCE'.",
    )
    reference_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class InventorySnapshot(AuditedModel):
    """Point-in-time balance for each (material, warehouse) pair.

    Generated daily at EOD (or on-demand) from the InventoryTransaction ledger.
    Used exclusively for fast report generation; never used as source of truth.
    The ledger always wins if there is a discrepancy.
    """

    __tablename__ = "inventory_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "material_id",
            "warehouse_id",
            "snapshot_date",
            name="uq_inv_snapshot_mat_wh_date",
        ),
        CheckConstraint("closing_balance >= 0", name="ck_inv_snapshot_balance_non_neg"),
        Index("ix_inv_snapshot_material_warehouse", "material_id", "warehouse_id"),
        Index("ix_inv_snapshot_date", "snapshot_date"),
    )

    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    snapshot_date: Mapped[object] = mapped_column(Date, nullable=False)
    closing_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        comment="Sum of all transactions up to and including snapshot_date.",
    )
    reserved_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        default=Decimal("0.0000"),
        comment="Quantity currently reserved but not yet dispatched.",
    )
