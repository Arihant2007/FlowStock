"""Master domain router — exposes RESTful endpoints for Warehouses, Materials, SKUs, and BOMs.

All endpoints are protected by RBAC via require_permission dependency.
Read operations require 'master:read'; write operations require 'master:write'.

Endpoints:
  GET    /master/warehouses              — list all warehouses (paginated)
  POST   /master/warehouses              — create a warehouse
  GET    /master/warehouses/{id}         — get a single warehouse
  PUT    /master/warehouses/{id}         — update a warehouse
  DELETE /master/warehouses/{id}         — soft-delete a warehouse

  GET    /master/materials               — list all materials (paginated)
  POST   /master/materials               — create a material
  GET    /master/materials/{id}          — get a single material
  PUT    /master/materials/{id}          — update a material
  DELETE /master/materials/{id}          — soft-delete a material

  GET    /master/skus                    — list all SKUs (paginated)
  POST   /master/skus                    — create a SKU
  GET    /master/skus/{id}               — get a single SKU
  PUT    /master/skus/{id}               — update a SKU
  DELETE /master/skus/{id}              — soft-delete a SKU
  GET    /master/skus/{id}/bom           — get the active BOM for a SKU (RM/PM split)

  POST   /master/boms/upload/preview     — preview a BOM Excel file (no commit)
  POST   /master/boms/upload/commit      — validate and commit a BOM Excel file
"""

import uuid

from fastapi import APIRouter, Depends, Query, UploadFile, status, Form, File
from sqlalchemy.orm import Session

from app.core.responses import ok, paginate
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.master.schemas import (
    BOMItemOut,
    BOMVersionOut,
    MaterialCreate,
    MaterialOut,
    MaterialUpdate,
    SKUCreate,
    SKUOut,
    SKUUpdate,
    WarehouseCreate,
    WarehouseOut,
    WarehouseUpdate,
)
from app.domains.master.service import MasterService
from app.infrastructure.database import get_db
from app.utils.file_validation import validate_upload_file

router = APIRouter(prefix="/master", tags=["Master Data"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bom_version_to_out(bom: object) -> BOMVersionOut:
    """Convert a BOMVersion ORM object to the output schema (RM/PM split)."""
    from app.domains.master.models import BOMItem, BOMVersion, Material

    assert isinstance(bom, BOMVersion)
    rm_items = []
    pm_items = []
    for item in bom.items:
        assert isinstance(item, BOMItem)
        mat = item.material
        assert isinstance(mat, Material)
        mat_type_name = mat.material_type.name if mat.material_type else "RM"
        from app.domains.master.schemas import (
            MaterialCategoryOut,
            MaterialGroupOut,
            MaterialTypeOut,
        )

        item_out = BOMItemOut(
            public_id=item.public_id,
            material=MaterialOut(
                public_id=mat.public_id,
                code=mat.code,
                name=mat.name,
                uom=mat.uom,
                category=MaterialCategoryOut.model_validate(mat.category)
                if mat.category
                else None,
                material_type=MaterialTypeOut.model_validate(mat.material_type)
                if mat.material_type
                else None,
                group=MaterialGroupOut.model_validate(mat.group) if mat.group else None,
                created_at=mat.created_at,
                updated_at=mat.updated_at,
            ),
            quantity_per_unit=item.quantity_per_unit,
            material_type=mat_type_name,
        )
        if mat_type_name == "PM":
            pm_items.append(item_out)
        else:
            rm_items.append(item_out)

    from app.domains.master.schemas import SKUOut

    return BOMVersionOut(
        public_id=bom.public_id,
        version_number=bom.version_number,
        notes=bom.notes,
        is_active=bom.is_active,
        sku=SKUOut.model_validate(bom.sku),
        rm_items=rm_items,
        pm_items=pm_items,
        created_at=bom.created_at,
    )


# ---------------------------------------------------------------------------
# Warehouse endpoints
# ---------------------------------------------------------------------------


@router.get("/warehouses", response_model=dict, status_code=status.HTTP_200_OK)
def list_warehouses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """List all warehouses (paginated)."""
    rows, meta = MasterService(db).list_warehouses(page=page, page_size=page_size)
    return paginate(
        [WarehouseOut.model_validate(r) for r in rows],
        page=meta.page,
        page_size=meta.page_size,
        total=meta.total,
    )


@router.post("/warehouses", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Create a new warehouse."""
    wh = MasterService(db).create_warehouse(payload, created_by=current_user.id)
    db.commit()
    return ok(
        WarehouseOut.model_validate(wh).model_dump(), message="Warehouse created."
    )


@router.get(
    "/warehouses/{warehouse_id}", response_model=dict, status_code=status.HTTP_200_OK
)
def get_warehouse(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """Get a single warehouse by public ID."""
    wh = MasterService(db).get_warehouse(str(warehouse_id))
    return ok(WarehouseOut.model_validate(wh).model_dump())


@router.put(
    "/warehouses/{warehouse_id}", response_model=dict, status_code=status.HTTP_200_OK
)
def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Update a warehouse. Requires current `version` for optimistic locking."""
    wh = MasterService(db).update_warehouse(
        str(warehouse_id), payload, updated_by=current_user.id
    )
    db.commit()
    return ok(
        WarehouseOut.model_validate(wh).model_dump(), message="Warehouse updated."
    )


@router.delete(
    "/warehouses/{warehouse_id}", response_model=dict, status_code=status.HTTP_200_OK
)
def delete_warehouse(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Soft-delete a warehouse."""
    MasterService(db).delete_warehouse(str(warehouse_id), deleted_by=current_user.id)
    db.commit()
    return ok({}, message="Warehouse deleted.")


# ---------------------------------------------------------------------------
# Material endpoints
# ---------------------------------------------------------------------------


@router.get("/materials", response_model=dict, status_code=status.HTTP_200_OK)
def list_materials(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """List all materials (paginated)."""
    rows, meta = MasterService(db).list_materials(page=page, page_size=page_size)
    return paginate(
        [MaterialOut.model_validate(r) for r in rows],
        page=meta.page,
        page_size=meta.page_size,
        total=meta.total,
    )


@router.post("/materials", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Create a new material."""
    mat = MasterService(db).create_material(payload, created_by=current_user.id)
    db.commit()
    return ok(MaterialOut.model_validate(mat).model_dump(), message="Material created.")


@router.get(
    "/materials/{material_id}", response_model=dict, status_code=status.HTTP_200_OK
)
def get_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """Get a single material by public ID."""
    mat = MasterService(db).get_material(str(material_id))
    return ok(MaterialOut.model_validate(mat).model_dump())


@router.put(
    "/materials/{material_id}", response_model=dict, status_code=status.HTTP_200_OK
)
def update_material(
    material_id: uuid.UUID,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Update a material. Requires current `version` for optimistic locking."""
    mat = MasterService(db).update_material(
        str(material_id), payload, updated_by=current_user.id
    )
    db.commit()
    return ok(MaterialOut.model_validate(mat).model_dump(), message="Material updated.")


@router.post(
    "/materials/{material_id}/archive", response_model=dict, status_code=status.HTTP_200_OK
)
def archive_material(
    material_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Soft-delete (archive) a material."""
    MasterService(db).archive_material(str(material_id), deleted_by=current_user.id)
    db.commit()
    return ok({}, message="Material archived.")


# ---------------------------------------------------------------------------
# Material Master Upload endpoints
# ---------------------------------------------------------------------------


@router.get("/materials/upload/template", response_class=status.HTTP_200_OK)
def download_material_template(
    _: User = Depends(require_permission("master:read")),
):
    """Download the Material Master Excel template."""
    import pandas as pd
    from io import BytesIO
    from fastapi.responses import StreamingResponse

    df = pd.DataFrame(columns=["Material Code", "Material Name", "UOM", "Category", "Material Type", "Group"])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Material Master")
    output.seek(0)

    headers = {
        "Content-Disposition": "attachment; filename=material_master_template.xlsx"
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post(
    "/materials/upload/preview", response_model=dict, status_code=status.HTTP_200_OK
)
async def preview_material_upload(
    file: UploadFile,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:write")),
) -> dict:
    """Upload a Material Master Excel file and receive a validation preview. No data is committed."""
    content = await validate_upload_file(file, db)
    preview = MasterService(db).preview_material_upload(
        content, file.filename or "upload.xlsx"
    )
    return ok(
        preview.model_dump(),
        message="Material Master file parsed. Review errors before committing.",
    )


@router.post("/materials/upload/commit", response_model=dict, status_code=status.HTTP_200_OK)
async def commit_material_upload(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Upload and commit a Material Master Excel file."""
    content = await validate_upload_file(file, db)
    # The entire request implicitly shares the single db session. 
    # Calling db.commit() at the end will either commit all upserts, or throw an error.
    result = MasterService(db).commit_material_upload(
        content, file.filename or "upload.xlsx", created_by=current_user.id
    )
    db.commit()
    return ok(
        result,
        message=f"Material Master upload committed. Created: {result['created']}, Updated: {result['updated']}, Skipped: {result['skipped']}.",
    )


@router.post("/materials/extract-from-bom", response_class=status.HTTP_200_OK)
async def extract_materials_from_bom(
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
    only_unknown: bool = Query(True, description="If true, only extracts materials that don't exist in the DB"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
):
    """Parse a BOM Excel file and generate a Material Master template containing the extracted materials."""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    from fastapi import HTTPException
    from app.core.errors import ValidationError

    content = None
    filename = None
    if file:
        content = await validate_upload_file(file, db)
        filename = file.filename or "bom.xlsx"

    if not content and not session_id:
        raise HTTPException(status_code=400, detail="Either file or session_id must be provided.")

    try:
        excel_bytes = MasterService(db).extract_materials_from_bom(
            file_bytes=content, filename=filename, session_id=session_id, only_unknown=only_unknown
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    output = BytesIO(excel_bytes)
    output.seek(0)
    
    headers = {
        "Content-Disposition": 'attachment; filename="extracted_materials.xlsx"'
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


# ---------------------------------------------------------------------------
# SKU endpoints
# ---------------------------------------------------------------------------


@router.get("/skus", response_model=dict, status_code=status.HTTP_200_OK)
def list_skus(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=5000),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """List all SKUs (paginated)."""
    rows, meta = MasterService(db).list_skus(page=page, page_size=page_size)
    return paginate(
        [SKUOut.model_validate(r) for r in rows],
        page=meta.page,
        page_size=meta.page_size,
        total=meta.total,
    )


@router.post("/skus", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_sku(
    payload: SKUCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Create a new SKU."""
    sku = MasterService(db).create_sku(payload, created_by=current_user.id)
    db.commit()
    return ok(SKUOut.model_validate(sku).model_dump(), message="SKU created.")


@router.get("/skus/options", response_model=dict, status_code=status.HTTP_200_OK)
def list_sku_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """Return all non-deleted SKUs as a lightweight options list (public_id, code, name only).

    Designed for dropdowns and autocompletes — omits description, timestamps, and
    pagination overhead. Always returns the full set; callers should not paginate.
    """
    from app.domains.master.schemas import SKUOptionOut

    rows, _ = MasterService(db).list_skus(page=1, page_size=5000)
    return ok([SKUOptionOut.model_validate(r).model_dump() for r in rows])


@router.get("/skus/{sku_id}", response_model=dict, status_code=status.HTTP_200_OK)
def get_sku(
    sku_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """Get a single SKU by public ID."""
    sku = MasterService(db).get_sku(str(sku_id))
    return ok(SKUOut.model_validate(sku).model_dump())


@router.put("/skus/{sku_id}", response_model=dict, status_code=status.HTTP_200_OK)
def update_sku(
    sku_id: uuid.UUID,
    payload: SKUUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Update a SKU. Requires current `version` for optimistic locking."""
    sku = MasterService(db).update_sku(str(sku_id), payload, updated_by=current_user.id)
    db.commit()
    return ok(SKUOut.model_validate(sku).model_dump(), message="SKU updated.")


@router.delete("/skus/{sku_id}", response_model=dict, status_code=status.HTTP_200_OK)
def delete_sku(
    sku_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Soft-delete a SKU."""
    MasterService(db).delete_sku(str(sku_id), deleted_by=current_user.id)
    db.commit()
    return ok({}, message="SKU deleted.")


@router.get("/skus/{sku_id}/bom", response_model=dict, status_code=status.HTTP_200_OK)
def get_active_bom(
    sku_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("master:read")),
) -> dict:
    """Return the currently active BOM version for a SKU, with items split into RM and PM."""
    bom = MasterService(db).get_active_bom(str(sku_id))
    return ok(_bom_version_to_out(bom).model_dump())


# ---------------------------------------------------------------------------
# BOM upload endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/boms/upload/preview", response_model=dict, status_code=status.HTTP_200_OK
)
async def preview_bom_upload(
    file: UploadFile | None = File(None),
    session_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Upload or resume a BOM Excel file preview."""
    content = None
    filename = None
    if file:
        content = await validate_upload_file(file, db)
        filename = file.filename or "upload.xlsx"

    preview = MasterService(db).preview_bom_upload(
        file_bytes=content,
        filename=filename,
        session_id=session_id,
        current_user_id=current_user.id,
    )
    db.commit()
    return ok(
        preview.model_dump(),
        message="BOM file parsed. Review errors before committing.",
    )


@router.post("/boms/upload/commit", response_model=dict, status_code=status.HTTP_200_OK)
async def commit_bom_upload(
    session_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    """Commit a staged BOM Excel file using its session ID."""
    result = MasterService(db).commit_bom_upload(
        session_id=session_id, current_user_id=current_user.id
    )
    db.commit()
    return ok(
        result,
        message="BOM import completed successfully.",
    )

@router.delete("/boms/upload/session/{session_id}", response_model=dict, status_code=status.HTTP_200_OK)
def cancel_bom_upload(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:write")),
) -> dict:
    MasterService(db).cancel_bom_upload(session_id, current_user.id)
    db.commit()
    return ok({}, message="BOM upload cancelled.")


@router.get("/boms/uploads/history", response_model=dict, status_code=status.HTTP_200_OK)
def get_bom_upload_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:read")),
) -> dict:
    """Retrieve history of BOM upload sessions."""
    from .schemas import BOMUploadSessionOut
    sessions = MasterService(db).list_bom_sessions()
    data = [BOMUploadSessionOut.model_validate(s).model_dump() for s in sessions]
    return ok(data, message="BOM upload history retrieved.")


@router.get("/dashboard/stats", response_model=dict, status_code=status.HTTP_200_OK)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("master:read")),
) -> dict:
    """Retrieve top-level dashboard statistics."""
    from .schemas import DashboardStatsOut
    stats = MasterService(db).get_dashboard_stats()
    return ok(DashboardStatsOut(**stats).model_dump(), message="Dashboard stats retrieved.")
