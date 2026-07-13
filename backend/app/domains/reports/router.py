import math
import uuid
from datetime import date
from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domains.auth.dependencies import require_permission
from app.domains.auth.models import User
from app.domains.inventory.models import InventoryTransaction
from app.domains.inventory.schemas import InventoryTransactionOut
from app.domains.inventory.service import InventoryService
from app.domains.master.models import SKU, Material, Warehouse
from app.domains.requests.models import (
    MaterialRequest,
    MaterialRequestItem,
    MaterialRequestSKU,
)
from app.domains.requests.schemas import MaterialRequestOut
from app.infrastructure.database import get_db
from app.utils.export import ExportFormat, generate_export

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/variance", response_model=dict, status_code=status.HTTP_200_OK)
def get_variance_report(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    warehouse: uuid.UUID | None = Query(None),
    material: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict:
    query = select(InventoryTransaction).where(InventoryTransaction.transaction_type == "ADJUSTMENT")

    if warehouse:
        wh = db.scalar(select(Warehouse).where(Warehouse.public_id == warehouse))
        if wh:
            query = query.where(
                (InventoryTransaction.source_warehouse_id == wh.id) |
                (InventoryTransaction.destination_warehouse_id == wh.id)
            )

    if material:
        mat = db.scalar(select(Material).where(Material.public_id == material))
        if mat:
            query = query.where(InventoryTransaction.material_id == mat.id)

    if from_date:
        query = query.where(InventoryTransaction.created_at >= str(from_date))
    if to_date:
        query = query.where(InventoryTransaction.created_at <= str(to_date) + " 23:59:59")

    query = query.order_by(InventoryTransaction.created_at.desc())

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())

    return {
        "success": True,
        "data": [InventoryTransactionOut.model_validate(tx).model_dump() for tx in items],
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 1,
        }
    }

@router.get("/variance/export", status_code=status.HTTP_200_OK)
def export_variance_report(
    format_type: ExportFormat = Query("excel", alias="format"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    warehouse: uuid.UUID | None = Query(None),
    material: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
):
    query = select(InventoryTransaction).where(InventoryTransaction.transaction_type == "ADJUSTMENT")

    if warehouse:
        wh = db.scalar(select(Warehouse).where(Warehouse.public_id == warehouse))
        if wh:
            query = query.where(
                (InventoryTransaction.source_warehouse_id == wh.id) |
                (InventoryTransaction.destination_warehouse_id == wh.id)
            )

    if material:
        mat = db.scalar(select(Material).where(Material.public_id == material))
        if mat:
            query = query.where(InventoryTransaction.material_id == mat.id)

    if from_date:
        query = query.where(InventoryTransaction.created_at >= str(from_date))
    if to_date:
        query = query.where(InventoryTransaction.created_at <= str(to_date) + " 23:59:59")

    query = query.order_by(InventoryTransaction.created_at.desc())
    transactions = db.scalars(query).all()

    data = []
    for tx in transactions:
        mat_code = db.scalar(select(Material.code).where(Material.id == tx.material_id)) if tx.material_id else ""
        wh_name = ""
        if tx.source_warehouse_id:
            wh_name = db.scalar(select(Warehouse.name).where(Warehouse.id == tx.source_warehouse_id)) or ""
        elif tx.destination_warehouse_id:
            wh_name = db.scalar(select(Warehouse.name).where(Warehouse.id == tx.destination_warehouse_id)) or ""

        data.append({
            "Date": tx.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "Transaction ID": f"TXN-{tx.id}",
            "Material": mat_code,
            "Warehouse": wh_name,
            "Quantity": str(tx.quantity),
            "Notes": tx.notes or "",
        })

    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["Date", "Transaction ID", "Material", "Warehouse", "Quantity", "Notes"])

    return generate_export(df, "Material_Variance", format_type)

@router.get("/inventory", response_model=dict, status_code=status.HTTP_200_OK)
def get_inventory_ledger(
    warehouse: uuid.UUID | None = Query(None),
    material: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict:
    svc = InventoryService(db)

    mat_query = select(Material).where(Material.deleted_at.is_(None))
    if material is not None:
        mat_query = mat_query.where(Material.public_id == material)

    wh_query = select(Warehouse).where(Warehouse.deleted_at.is_(None))
    if warehouse is not None:
        wh_query = wh_query.where(Warehouse.public_id == warehouse)

    materials = list(db.scalars(mat_query).all())
    warehouses = list(db.scalars(wh_query).all())

    txs = db.scalars(select(InventoryTransaction)).all()
    pairs = set()
    for tx in txs:
        if tx.transaction_type in ["RECEIPT", "TRANSFER_IN", "ADJUSTMENT"] and tx.destination_warehouse_id:
            pairs.add((tx.material_id, tx.destination_warehouse_id))
        if tx.transaction_type in ["DISPATCH", "TRANSFER_OUT", "RESERVATION"] and tx.source_warehouse_id:
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

    balances.sort(key=lambda x: (x["warehouse_name"], x["material_code"]))

    total = len(balances)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = balances[start:end]

    return {
        "success": True,
        "data": paginated,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 1,
        }
    }

@router.get("/inventory/export", status_code=status.HTTP_200_OK)
def export_inventory_ledger(
    format_type: ExportFormat = Query("excel", alias="format"),
    warehouse: uuid.UUID | None = Query(None),
    material: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
):
    resp = get_inventory_ledger(warehouse=warehouse, material=material, page=1, page_size=1000000, db=db, _=_)
    data = resp["data"]

    export_data = []
    for row in data:
        export_data.append({
            "Warehouse": row["warehouse_name"],
            "Material Code": row["material_code"],
            "Material Name": row["material_name"],
            "UoM": row["uom"],
            "Available Balance": row["available_balance"],
            "Reserved Balance": row["reserved_balance"]
        })

    df = pd.DataFrame(export_data)
    if df.empty:
        df = pd.DataFrame(columns=["Warehouse", "Material Code", "Material Name", "UoM", "Available Balance", "Reserved Balance"])

    return generate_export(df, "Current_Inventory_Ledger", format_type)

@router.get("/requests", response_model=dict, status_code=status.HTTP_200_OK)
def get_requests_report(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict:
    query = select(MaterialRequest).where(MaterialRequest.deleted_at.is_(None))

    if status_filter:
        query = query.where(MaterialRequest.status == status_filter)

    if from_date:
        query = query.where(MaterialRequest.request_date >= from_date)
    if to_date:
        query = query.where(MaterialRequest.request_date <= to_date)

    query = query.order_by(MaterialRequest.request_date.desc())

    query = query.options(
        selectinload(MaterialRequest.skus).selectinload(MaterialRequestSKU.items).joinedload(MaterialRequestItem.material).joinedload(Material.material_type),
        selectinload(MaterialRequest.skus).joinedload(MaterialRequestSKU.sku)
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())

    results = []
    for req in items:
        # Setup material types for schema
        for sku in req.skus:
            for item in sku.items:
                item.material_type = item.material.material_type.name if item.material and hasattr(item.material, "material_type") and item.material.material_type else "RM"  # type: ignore[attr-defined]
        results.append(MaterialRequestOut.model_validate(req).model_dump())

    return {
        "success": True,
        "data": results,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 1,
        }
    }

@router.get("/requests/export", status_code=status.HTTP_200_OK)
def export_requests_report(
    format_type: ExportFormat = Query("excel", alias="format"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
):
    query = select(MaterialRequest).where(MaterialRequest.deleted_at.is_(None))

    if status_filter:
        query = query.where(MaterialRequest.status == status_filter)

    if from_date:
        query = query.where(MaterialRequest.request_date >= from_date)
    if to_date:
        query = query.where(MaterialRequest.request_date <= to_date)

    query = query.order_by(MaterialRequest.request_date.desc())
    query = query.options(
        selectinload(MaterialRequest.skus).selectinload(MaterialRequestSKU.items).joinedload(MaterialRequestItem.material),
        selectinload(MaterialRequest.skus).joinedload(MaterialRequestSKU.sku)
    )
    requests = db.scalars(query).all()

    data = []
    for req in requests:
        for sku in req.skus:
            sku_code = sku.sku.code if sku.sku else ""
            for item in sku.items:
                mat_code = item.material.code if item.material else ""

                data.append({
                    "Request ID": f"REQ-{req.id}",
                    "Date": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
                    "Status": req.status,
                    "Business Date": req.request_date.strftime("%Y-%m-%d") if req.request_date else "",
                    "SKU": sku_code,
                    "Planned FG Qty": str(sku.planned_production_qty),
                    "Material": mat_code,
                    "Gross Req": str(item.gross_required_qty),
                    "Remaining Inv": str(item.remaining_from_previous_day),
                    "Net Req": str(item.requested_qty),
                    "Approved": str(item.approved_qty or 0),
                    "Dispatched": str(item.dispatched_qty or 0),
                    "Received": str(item.received_qty or 0)
                })

    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Request ID", "Date", "Status", "Business Date", "SKU", "Planned FG Qty",
            "Material", "Gross Req", "Remaining Inv", "Net Req", "Approved", "Dispatched", "Received"
        ])

    return generate_export(df, "Material_Requests", format_type)

@router.get("/production", response_model=dict, status_code=status.HTTP_200_OK)
def get_production_report(
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    sku: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
) -> dict:
    query = select(MaterialRequest).where(MaterialRequest.deleted_at.is_(None))
    query = query.where(MaterialRequest.status.in_(["APPROVED", "DISPATCHED", "RECEIVED", "CLOSED"]))

    if from_date:
        query = query.where(MaterialRequest.request_date >= from_date)
    if to_date:
        query = query.where(MaterialRequest.request_date <= to_date)

    query = query.order_by(MaterialRequest.request_date.desc())
    query = query.options(
        selectinload(MaterialRequest.skus).selectinload(MaterialRequestSKU.items).joinedload(MaterialRequestItem.material),
        selectinload(MaterialRequest.skus).joinedload(MaterialRequestSKU.sku)
    )
    requests = db.scalars(query).all()

    data = []

    sku_filter = None
    if sku:
        sku_filter = db.scalar(select(SKU).where(SKU.public_id == sku))

    for req in requests:
        for sku_obj in req.skus:
            if sku_filter and sku_obj.sku_id != sku_filter.id:
                continue

            sku_code = sku_obj.sku.code if sku_obj.sku else ""

            for item in sku_obj.items:
                mat_code = item.material.code if item.material else ""

                data.append({
                    "date": req.request_date.strftime("%Y-%m-%d"),
                    "sku": sku_code,
                    "material": mat_code,
                    "planned_fg_qty": str(sku_obj.planned_production_qty),
                    "gross_requirement": str(item.gross_required_qty),
                    "remaining_inventory": str(item.remaining_from_previous_day),
                    "net_requested": str(item.requested_qty),
                    "approved": str(item.approved_qty or 0),
                    "dispatched": str(item.dispatched_qty or 0),
                    "received": str(item.received_qty or 0),
                    "consumed": str(item.received_qty or 0) if req.status == "CLOSED" else "0"
                })

    total = len(data)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = data[start:end]

    return {
        "success": True,
        "data": paginated,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if page_size else 1,
        }
    }

@router.get("/production/export", status_code=status.HTTP_200_OK)
def export_production_report(
    format_type: ExportFormat = Query("excel", alias="format"),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    sku: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("reports:read")),
):
    resp = get_production_report(from_date=from_date, to_date=to_date, sku=sku, page=1, page_size=1000000, db=db, _=_)
    data = resp["data"]

    export_data = []
    for row in data:
        export_data.append({
            "Date": row["date"],
            "SKU": row["sku"],
            "Material": row["material"],
            "Planned FG Qty": row["planned_fg_qty"],
            "Gross Requirement": row["gross_requirement"],
            "Remaining Inventory": row["remaining_inventory"],
            "Net Requested": row["net_requested"],
            "Approved": row["approved"],
            "Dispatched": row["dispatched"],
            "Received": row["received"],
            "Consumed": row["consumed"],
        })

    df = pd.DataFrame(export_data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Date", "SKU", "Material", "Planned FG Qty", "Gross Requirement",
            "Remaining Inventory", "Net Requested", "Approved", "Dispatched",
            "Received", "Consumed"
        ])

    return generate_export(df, "Daily_Production_Report", format_type)
