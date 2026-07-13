"""Requests domain Pydantic schemas.

Business logic changes reflected here:
  1. DRAFT state removed — requests start immediately as SUBMITTED.
  2. ODS API accepts SKU + planned_production_qty + remaining quantities split
     into separate RM (Raw Material) and PM (Packaging Material) buckets.
     The backend calculates gross and net material quantities from the active BOM.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Remaining material inputs (split by type per business change #2)
# ---------------------------------------------------------------------------


class RequestSKUInput(BaseModel):
    """One SKU line within the morning request submission.

    The backend resolves the active BOM and computes:
      gross_required = bom_qty_per_unit × planned_production_qty
      remaining = ODS current inventory
      net_requested  = max(gross_required - remaining, 0)
    """

    sku_public_id: uuid.UUID
    planned_production_qty: Decimal = Field(gt=Decimal("0"), decimal_places=4)


class CreateRequestPayload(BaseModel):
    """POST /requests — creates a request that immediately enters SUBMITTED status."""

    request_date: date
    ods_warehouse_public_id: uuid.UUID
    notes: str = Field(default="", max_length=2000)
    skus: list[RequestSKUInput] = Field(..., min_length=1)


class RequestPreviewPayload(CreateRequestPayload):
    """POST /requests/preview — returns calculation without saving."""

    pass


class RequestPreviewItemOut(BaseModel):
    material_public_id: uuid.UUID
    material_name: str
    material_code: str
    material_type: str
    gross_required_qty: Decimal
    remaining_from_previous_day: Decimal
    requested_qty: Decimal


class RequestPreviewSKUOut(BaseModel):
    sku_public_id: uuid.UUID
    sku_name: str
    sku_code: str
    planned_production_qty: Decimal
    items: list[RequestPreviewItemOut]


class RequestPreviewOut(BaseModel):
    skus: list[RequestPreviewSKUOut]


# ---------------------------------------------------------------------------
# Approval payload
# ---------------------------------------------------------------------------


class ApprovalItemInput(BaseModel):
    """Approved quantity for one MaterialRequestItem line."""

    material_request_item_public_id: uuid.UUID
    approved_qty: Decimal = Field(ge=Decimal("0"), decimal_places=4)


class ApproveRequestPayload(BaseModel):
    """PUT /requests/{id}/approve — RMPM approval payload."""

    rmpm_warehouse_public_id: uuid.UUID
    items: list[ApprovalItemInput] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class MaterialRequestItemOut(BaseModel):
    """Serialized MaterialRequestItem line."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    material_id: int
    material_type: str = Field(
        default="RM",
        description="'RM' or 'PM' — resolved from the material's type at request time.",
    )
    gross_required_qty: Decimal
    remaining_from_previous_day: Decimal
    requested_qty: Decimal
    approved_qty: Decimal | None
    dispatched_qty: Decimal | None
    received_qty: Decimal | None


class MaterialRequestSKUOut(BaseModel):
    """Serialized MaterialRequestSKU with nested items."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    sku_id: int
    planned_production_qty: Decimal
    items: list[MaterialRequestItemOut]


class MaterialRequestOut(BaseModel):
    """Full serialized MaterialRequest with all nested data."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    request_date: date
    status: str
    notes: str
    ods_warehouse_id: int
    rmpm_warehouse_id: int | None
    skus: list[MaterialRequestSKUOut]
    created_at: datetime
    updated_at: datetime | None


class MaterialRequestListItem(BaseModel):
    """Lightweight summary for list responses."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    request_date: date
    status: str
    notes: str
    created_at: datetime
