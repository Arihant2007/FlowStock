"""Master domain Pydantic schemas.

Provides request/response models for:
  - Warehouses (ODS / RMPM storage locations)
  - Materials (raw materials and packaging materials)
  - SKUs (finished goods stock-keeping units)
  - BOM Versions and Items (with explicit RM/PM distinction)
  - BOM Excel upload preview and commit
"""

import uuid
from datetime import datetime, date
from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------


class WarehouseCreate(BaseModel):
    """Payload for creating a new warehouse."""

    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(ODS|RMPM)$")
    description: str = Field(default="", max_length=1000)


class WarehouseUpdate(BaseModel):
    """Payload for updating an existing warehouse (partial update supported)."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    version: int = Field(
        ..., ge=1, description="Current version for optimistic locking."
    )


class WarehouseOut(BaseModel):
    """Serialized Warehouse response."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    name: str
    type: str
    description: str
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Material Classifications
# ---------------------------------------------------------------------------


class MaterialCategoryOut(BaseModel):
    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    name: str


class MaterialTypeOut(BaseModel):
    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    name: str


class MaterialGroupOut(BaseModel):
    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    name: str


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------


class MaterialCreate(BaseModel):
    """Payload for creating a new material."""

    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    uom: str = Field(..., min_length=1, max_length=50)
    category_public_id: uuid.UUID
    type_public_id: uuid.UUID
    group_public_id: uuid.UUID | None = None


class MaterialUpdate(BaseModel):
    """Payload for updating an existing material."""

    name: str | None = Field(None, min_length=1, max_length=255)
    uom: str | None = Field(None, min_length=1, max_length=50)
    category_public_id: uuid.UUID | None = None
    type_public_id: uuid.UUID | None = None
    group_public_id: uuid.UUID | None = None
    version: int = Field(..., ge=1)


class MaterialOut(BaseModel):
    """Serialized Material response."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    code: str
    name: str
    uom: str
    category: MaterialCategoryOut | None = None
    material_type: MaterialTypeOut | None = None
    group: MaterialGroupOut | None = None
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# SKU
# ---------------------------------------------------------------------------


class SKUCreate(BaseModel):
    """Payload for creating a new SKU."""

    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class SKUUpdate(BaseModel):
    """Payload for updating an existing SKU."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    version: int = Field(..., ge=1)


class SKUOut(BaseModel):
    """Serialized SKU response."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    code: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime | None


class SKUOptionOut(BaseModel):
    """Lightweight SKU projection for dropdown / autocomplete use.

    Returns only the three fields needed to render a select option —
    omits description, timestamps, and audit columns to keep the payload small.
    """

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    code: str
    name: str


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------


class BOMItemOut(BaseModel):
    """Serialized BOM item line with material type classification."""

    public_id: uuid.UUID
    material: MaterialOut
    quantity_per_unit: Decimal
    material_type: str = Field(
        description="'RM' or 'PM' — resolved from material.material_type.name"
    )


class BOMVersionOut(BaseModel):
    """Serialized BOM version with all item lines split by RM and PM."""

    public_id: uuid.UUID
    version_number: int
    notes: str
    is_active: bool
    sku: SKUOut
    rm_items: list[BOMItemOut] = Field(
        default_factory=list, description="Raw material lines."
    )
    pm_items: list[BOMItemOut] = Field(
        default_factory=list, description="Packaging material lines."
    )
    created_at: datetime


# ---------------------------------------------------------------------------
# BOM Upload
# ---------------------------------------------------------------------------


class BOMUploadRowResult(BaseModel):
    """Validation result for a single material line in the BOM upload file."""

    sheet_name: str
    row_number: int
    sku_code: str
    material_code: str
    material_desc: str
    uom: str
    quantity_per_unit: str
    status: str = Field(description="'valid', 'error', 'warning', or 'pending_material'")
    message: str = ""


class BOMUploadPreview(BaseModel):
    """Preview response returned after BOM Excel file validation (before commit)."""

    total_rows: int
    valid_rows: int
    error_rows: int
    pending_rows: int = 0

    # New reporting fields
    existing_skus: list[str]
    new_skus: list[str]
    existing_materials: list[str]
    unknown_materials: list[str]
    duplicate_material_codes: list[str]
    duplicate_sku_codes: list[str]
    empty_sheets: list[str]

    rows: list[BOMUploadRowResult]
    errors: list[str]
    warnings: list[str] = Field(default_factory=list)
    skus_affected: list[str] = Field(
        description="SKU codes that will receive a new BOM version."
    )
    session_id: str | None = None
    session_status: str | None = None


class BOMUploadSessionOut(BaseModel):
    """Serialized BOM upload session history."""

    public_id: uuid.UUID
    filename: str
    status: str
    created_at: datetime
    expires_at: datetime
    import_results: dict | None = None
    warnings: list[str] | None = None


class InventoryUploadStats(BaseModel):
    snapshot_date: date | None = None
    upload_time: datetime | None = None
    uploaded_by: str | None = None
    warehouse_name: str | None = None
    version: int | None = None
    total_materials: int = 0
    matched_count: int = 0
    variance_count: int = 0

class DashboardStatsOut(BaseModel):
    """Top-level dashboard statistics."""

    total_materials: int
    total_skus: int
    total_bom_versions: int
    total_bom_items: int
    last_import_at: datetime | None = None
    inventory_upload: InventoryUploadStats | None = None


# Material Master Upload
# ---------------------------------------------------------------------------


class MaterialUploadRowResult(BaseModel):
    """Validation result for a single row in the Material Master upload file."""

    row_number: int
    material_code: str
    material_name: str | None = None
    uom: str | None = None
    category: str | None = None
    material_type: str | None = None
    group: str | None = None
    status: str = Field(description="'valid', 'error', 'duplicate', 'skipped'")
    message: str = ""


class MaterialUploadPreview(BaseModel):
    """Preview response returned after Material Master Excel validation."""

    total_rows: int
    valid_rows: int
    error_rows: int
    skipped_rows_count: int = 0

    new_materials: list[str]
    updated_materials: list[str]
    duplicate_material_codes: list[str]
    invalid_rows: list[str] = Field(default_factory=list)
    skipped_rows: list[str] = Field(default_factory=list)

    rows: list[MaterialUploadRowResult]
    errors: list[str]
    warnings: list[str] = Field(default_factory=list)
