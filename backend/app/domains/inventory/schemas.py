"""Inventory domain Pydantic schemas."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InventoryBalanceOut(BaseModel):
    """Current balance for a single (material, warehouse) pair."""

    material_public_id: uuid.UUID
    material_code: str
    material_name: str
    warehouse_public_id: uuid.UUID
    warehouse_name: str
    available_balance: Decimal = Field(decimal_places=4)
    reserved_balance: Decimal = Field(decimal_places=4)
    uom: str


class InventoryTransactionOut(BaseModel):
    """Serialized representation of a single ledger entry."""

    model_config = {"from_attributes": True}

    id: int
    transaction_type: str
    quantity: Decimal
    reference_type: str | None
    reference_id: int | None
    notes: str
    created_at: datetime
    created_by: int


class OpeningBalanceUploadPreview(BaseModel):
    """Preview response returned after Excel upload validation (before commit)."""

    total_rows: int
    valid_rows: int
    error_rows: int
    warning_rows: int
    
    total_materials: int = 0
    total_quantity: Decimal = Field(default=Decimal("0"))
    duplicates: int = 0
    unknown_materials: int = 0
    negative_quantities: int = 0
    
    rows: list[dict]  # Each row contains raw values + validation status.
    warnings: list[str]
    errors: list[str]


class EODCountItem(BaseModel):
    """A single EOD physical count entry for one material."""

    material_public_id: uuid.UUID
    warehouse_public_id: uuid.UUID
    actual_quantity: Decimal = Field(gt=Decimal("0"), decimal_places=4)


class EODCountRequest(BaseModel):
    """Payload for POST /inventory/eod-count — submitted by ODS operator."""

    count_date: date
    items: list[EODCountItem] = Field(..., min_length=1)


class VarianceReportItemOut(BaseModel):
    """A single item in the variance report."""
    material_public_id: uuid.UUID
    material_code: str
    material_name: str
    warehouse_public_id: uuid.UUID
    warehouse_name: str
    snapshot_date: date | None
    snapshot_balance: Decimal = Field(decimal_places=4)
    current_ledger_balance: Decimal = Field(decimal_places=4)
    variance: Decimal = Field(decimal_places=4)
    variance_percentage: str
    uom: str
