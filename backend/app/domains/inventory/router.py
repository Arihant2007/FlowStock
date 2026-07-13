"""Inventory domain router — ledger queries, opening balance upload, and EOD reconciliation.

Endpoints:
  POST /inventory/upload/preview     — Parse and validate an opening balance Excel (no commit)
  POST /inventory/upload/commit      — Reconcile and commit opening balance snapshot
  POST /inventory/eod-count          — Submit physical EOD count and reconcile adjustments
  GET  /inventory/balances           — List current available + reserved balances
  GET  /inventory/transactions       — Paginated ledger transaction history
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import ok, paginate
from app.domains.audit.service import AuditService
from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.inventory.models import InventoryTransaction
from app.domains.inventory.schemas import (
    EODCountRequest,
    InventoryTransactionOut,
)
from app.domains.inventory.service import InventoryService
from app.infrastructure.database import get_db
from app.utils.file_validation import validate_upload_file

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ---------------------------------------------------------------------------
# Opening Balance Upload (snapshot-based)
# ---------------------------------------------------------------------------


@router.post("/upload/preview", response_model=dict, status_code=status.HTTP_200_OK)
async def preview_opening_balance(
    file: UploadFile,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:upload")),
) -> dict:
    """Parse an opening balance Excel file and return a row-by-row validation preview.

    No data is committed. Review the preview before calling /upload/commit.

    Required columns: Material Code, Quantity, UoM, Warehouse, Date (DD/MM/YYYY)
    """
    content = await validate_upload_file(file, db)
    preview = InventoryService(db).preview_opening_balance(
        content, file.filename or "upload.xlsx"
    )
    return ok(
        preview.model_dump(),
        message="File parsed. Review errors and warnings before committing.",
    )


@router.post("/upload/commit", response_model=dict, status_code=status.HTTP_200_OK)
async def commit_opening_balance(
    file: UploadFile,
    ignore_warnings: bool = Query(
        False, description="Set to true to commit despite warnings."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:upload")),
) -> dict:
    """Commit an opening balance Excel as a reconciled inventory snapshot.

    For each row:
      1. Compares uploaded quantity with the current ledger balance.
      2. Creates an ADJUSTMENT transaction if a delta is found.
      3. Stores (or updates) the snapshot in inventory_snapshots.

    An audit log entry is written on success.
    """
    content = await validate_upload_file(file, db)
    svc = InventoryService(db)

    is_admin = current_user.role.name.lower() == "admin"

    result = svc.commit_opening_balance_snapshot(
        content,
        file.filename or "upload.xlsx",
        committed_by=current_user.id,
        ignore_warnings=ignore_warnings,
        is_admin=is_admin,
    )
    AuditService(db).log_action(
        action="INVENTORY_UPLOAD_COMMITTED",
        user_id=current_user.id,
        details=result,
    )
    db.commit()
    return ok(
        result,
        message=(
            f"Opening balance committed. "
            f"{result['adjustments_created']} adjustment(s) created, "
            f"{result['snapshots_upserted']} snapshot(s) stored."
        ),
    )


# ---------------------------------------------------------------------------
# EOD Physical Count
# ---------------------------------------------------------------------------


@router.post("/eod-count", response_model=dict, status_code=status.HTTP_200_OK)
def submit_eod_count(
    payload: EODCountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory:adjust")),
) -> dict:
    """Submit physical EOD counts and reconcile via adjustment transactions.

    For each item, the current ledger balance is compared with the submitted
    physical count. If there is a discrepancy, an ADJUSTMENT transaction is created.
    """
    from app.domains.master.models import Material, Warehouse

    svc = InventoryService(db)
    adjustments: list[dict[str, Any]] = []

    for item in payload.items:
        material = db.scalar(
            select(Material)
            .where(Material.public_id == item.material_public_id)
            .where(Material.deleted_at.is_(None))
        )
        if material is None:
            from app.core.errors import NotFoundError

            raise NotFoundError(f"Material {item.material_public_id} not found.")

        warehouse = db.scalar(
            select(Warehouse)
            .where(Warehouse.public_id == item.warehouse_public_id)
            .where(Warehouse.deleted_at.is_(None))
        )
        if warehouse is None:
            from app.core.errors import NotFoundError

            raise NotFoundError(f"Warehouse {item.warehouse_public_id} not found.")

        current_balance = svc.get_balance(material.id, warehouse.id)
        tx = svc.record_adjustment(
            material_id=material.id,
            warehouse_id=warehouse.id,
            expected=current_balance,
            actual=item.actual_quantity,
            reference_id=0,
            adjusted_by=current_user.id,
        )
        adjustments.append(
            {
                "material_code": material.code,
                "warehouse_name": warehouse.name,
                "previous_balance": str(current_balance),
                "actual_count": str(item.actual_quantity),
                "delta": str(item.actual_quantity - current_balance),
                "adjustment_created": tx is not None,
            }
        )

    AuditService(db).log_action(
        action="EOD_COUNT_SUBMITTED",
        user_id=current_user.id,
        details={"count_date": str(payload.count_date), "items": len(payload.items)},
    )
    db.commit()
    return ok(
        {"count_date": str(payload.count_date), "adjustments": adjustments},
        message=f"EOD count processed. {sum(1 for a in adjustments if a['adjustment_created'])} adjustment(s) created.",
    )


# ---------------------------------------------------------------------------
# Balance query
# ---------------------------------------------------------------------------


@router.get("/balances", response_model=dict, status_code=status.HTTP_200_OK)
def list_balances(
    warehouse_public_id: uuid.UUID | None = Query(
        None, description="Filter by warehouse."
    ),
    material_public_id: uuid.UUID | None = Query(
        None, description="Filter by material."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
) -> dict:
    """Return current available and reserved balances per (material, warehouse) pair."""
    from decimal import Decimal

    from sqlalchemy import func

    from app.domains.inventory.models import InventoryTransaction
    from app.domains.master.models import Material, Warehouse

    svc = InventoryService(db)

    # Build base set of (material, warehouse) pairs from transactions
    mat_query = select(Material).where(Material.deleted_at.is_(None))
    if material_public_id is not None:
        mat_query = mat_query.where(Material.public_id == material_public_id)

    wh_query = select(Warehouse).where(Warehouse.deleted_at.is_(None))
    if warehouse_public_id is not None:
        wh_query = wh_query.where(Warehouse.public_id == warehouse_public_id)

    materials = list(db.scalars(mat_query).all())
    warehouses = list(db.scalars(wh_query).all())

    txs = db.scalars(select(InventoryTransaction)).all()
    pairs = set()
    for tx in txs:
        if (
            tx.transaction_type in ["RECEIPT", "TRANSFER_IN", "ADJUSTMENT"]
            and tx.destination_warehouse_id
        ):
            pairs.add((tx.material_id, tx.destination_warehouse_id))
        if (
            tx.transaction_type in ["DISPATCH", "TRANSFER_OUT", "RESERVATION"]
            and tx.source_warehouse_id
        ):
            pairs.add((tx.material_id, tx.source_warehouse_id))

    mat_map = {m.id: m for m in materials}
    wh_map = {w.id: w for w in warehouses}

    balances = []
    for mat_id, wh_id in pairs:
        if mat_id not in mat_map or wh_id is None or wh_id not in wh_map:
            continue
        mat = mat_map[mat_id]
        wh = wh_map[wh_id]
        avail = svc.get_balance(mat_id, wh_id)
        # Reserved balance = sum of active RESERVATION transactions
        reserved: Decimal = db.scalar(
            select(func.coalesce(func.sum(InventoryTransaction.quantity), Decimal("0")))
            .where(InventoryTransaction.material_id == mat_id)
            .where(InventoryTransaction.source_warehouse_id == wh_id)
            .where(InventoryTransaction.transaction_type == "RESERVATION")
        ) or Decimal("0")

        balances.append(
            {
                "material_public_id": str(mat.public_id),
                "material_code": mat.code,
                "material_name": mat.name,
                "uom": mat.uom,
                "warehouse_public_id": str(wh.public_id),
                "warehouse_name": wh.name,
                "available_balance": str(avail),
                "reserved_balance": str(reserved),
            }
        )

    total = len(balances)
    start = (page - 1) * page_size
    page_data = balances[start : start + page_size]
    return paginate(page_data, page=page, page_size=page_size, total=total)


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------


@router.get("/transactions", response_model=dict, status_code=status.HTTP_200_OK)
def list_transactions(
    material_public_id: uuid.UUID | None = Query(None),
    warehouse_public_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("inventory:read")),
) -> dict:
    """Return a paginated list of inventory ledger transactions."""
    from sqlalchemy import func

    from app.domains.master.models import Material, Warehouse

    stmt = select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc())

    if material_public_id is not None:
        mat = db.scalar(
            select(Material).where(Material.public_id == material_public_id)
        )
        if mat:
            stmt = stmt.where(InventoryTransaction.material_id == mat.id)

    if warehouse_public_id is not None:
        wh = db.scalar(
            select(Warehouse).where(Warehouse.public_id == warehouse_public_id)
        )
        if wh:
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    InventoryTransaction.source_warehouse_id == wh.id,
                    InventoryTransaction.destination_warehouse_id == wh.id,
                )
            )

    if transaction_type is not None:
        stmt = stmt.where(
            InventoryTransaction.transaction_type == transaction_type.upper()
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.scalar(count_stmt) or 0
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return paginate(
        [InventoryTransactionOut.model_validate(r).model_dump() for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )
