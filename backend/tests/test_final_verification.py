import datetime
import uuid
from decimal import Decimal

import pytest

from app.core.errors import ValidationError
from app.domains.inventory.models import InventorySnapshot, InventoryTransaction
from app.domains.master.models import (
    SKU,
    Material,
    MaterialCategory,
    MaterialType,
    Warehouse,
)
from app.domains.requests.schemas import CreateRequestPayload, RequestSKUInput
from app.domains.requests.service import RequestService


def setup_master_data(db):
    """Setup minimum master data for tests."""
    cat = MaterialCategory(name="Raw Material", public_id=uuid.uuid4(), created_by=1)
    typ = MaterialType(name="Ingredient", public_id=uuid.uuid4(), created_by=1)
    db.add(cat)
    db.add(typ)
    db.flush()

    mat = Material(code="MAT-POTATO", name="Potato", uom="KG", category_id=cat.id, type_id=typ.id, public_id=uuid.uuid4(), created_by=1)
    sku1 = SKU(code="SKU-CHIPS-1", name="Chips 1", public_id=uuid.uuid4(), created_by=1)
    sku2 = SKU(code="SKU-CHIPS-2", name="Chips 2", public_id=uuid.uuid4(), created_by=1)
    ods = Warehouse(name="ODS", type="ODS", public_id=uuid.uuid4(), created_by=1)
    rmpm = Warehouse(name="RMPM", type="RMPM", public_id=uuid.uuid4(), created_by=1)

    db.add_all([mat, sku1, sku2, ods, rmpm])
    db.flush()

    # Need BOMs
    from app.domains.master.models import BOMItem, BOMVersion
    bom1 = BOMVersion(sku_id=sku1.id, version_number=1, is_active=True, created_by=1)
    bom2 = BOMVersion(sku_id=sku2.id, version_number=1, is_active=True, created_by=1)
    db.add_all([bom1, bom2])
    db.flush()

    # Both SKUs use potato. SKU1 uses 5kg per unit, SKU2 uses 10kg per unit.
    db.add(BOMItem(bom_version_id=bom1.id, material_id=mat.id, quantity_per_unit=Decimal("5"), created_by=1))
    db.add(BOMItem(bom_version_id=bom2.id, material_id=mat.id, quantity_per_unit=Decimal("10"), created_by=1))
    db.flush()

    return {
        "mat": mat, "sku1": sku1, "sku2": sku2, "ods": ods, "rmpm": rmpm
    }

def test_snapshot_date_validation(db):
    data = setup_master_data(db)
    svc = RequestService(db)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    payload = CreateRequestPayload(
        request_date=today,
        ods_warehouse_public_id=data["ods"].public_id,
        skus=[RequestSKUInput(sku_public_id=data["sku1"].public_id, planned_production_qty=Decimal("10"))]
    )

    # 1. Missing snapshot should succeed with remaining=0
    req1 = svc.create_request(payload, created_by=1)
    assert req1.status == "SUBMITTED"
    assert req1.skus[0].items[0].remaining_from_previous_day == Decimal("0")

    # 2. Today's snapshot should also succeed with remaining=0 (it expects yesterday's)
    db.add(InventorySnapshot(material_id=data["mat"].id, warehouse_id=data["ods"].id, snapshot_date=today, closing_balance=Decimal("10"), created_by=1))
    db.flush()
    req2 = svc.create_request(payload, created_by=1)
    assert req2.status == "SUBMITTED"
    assert req2.skus[0].items[0].remaining_from_previous_day == Decimal("0")

    # 3. Yesterday's snapshot should succeed and use the remaining balance
    db.add(InventorySnapshot(material_id=data["mat"].id, warehouse_id=data["ods"].id, snapshot_date=yesterday, closing_balance=Decimal("10"), created_by=1))
    db.add(InventoryTransaction(material_id=data["mat"].id, destination_warehouse_id=data["ods"].id, transaction_type="RECEIPT", quantity=Decimal("10"), created_by=1))
    db.flush()

    req3 = svc.create_request(payload, created_by=1)
    assert req3.status == "SUBMITTED"
    assert req3.skus[0].items[0].remaining_from_previous_day == Decimal("10")

def test_aggregation_and_lifecycle(db):
    data = setup_master_data(db)
    svc = RequestService(db)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # Give ODS 100 kg of Potato in yesterday's snapshot AND transactions
    db.add(InventorySnapshot(material_id=data["mat"].id, warehouse_id=data["ods"].id, snapshot_date=yesterday, closing_balance=Decimal("100"), created_by=1))
    db.add(InventoryTransaction(material_id=data["mat"].id, destination_warehouse_id=data["ods"].id, transaction_type="RECEIPT", quantity=Decimal("100"), created_by=1))

    # Give RMPM 1000 kg of Potato
    db.add(InventoryTransaction(material_id=data["mat"].id, destination_warehouse_id=data["rmpm"].id, transaction_type="RECEIPT", quantity=Decimal("1000"), created_by=1))
    db.flush()

    # Create Request
    # SKU1: 10 units * 5kg = 50kg gross
    # SKU2: 10 units * 10kg = 100kg gross
    # Total Gross = 150kg
    # ODS Remaining = 100kg
    # Total Net = 50kg
    payload = CreateRequestPayload(
        request_date=today,
        ods_warehouse_public_id=data["ods"].public_id,
        skus=[
            RequestSKUInput(sku_public_id=data["sku1"].public_id, planned_production_qty=Decimal("10")),
            RequestSKUInput(sku_public_id=data["sku2"].public_id, planned_production_qty=Decimal("10")),
        ]
    )
    req = svc.create_request(payload, created_by=1)

    total_net = sum(item.requested_qty for sku in req.skus for item in sku.items)
    assert total_net == Decimal("50.0000"), f"Total net was {total_net}"

    # APPROVE (reserves inventory)
    from app.domains.requests.schemas import ApproveRequestPayload
    approve_items = []
    for sku in req.skus:
        for item in sku.items:
            approve_items.append({"material_public_id": item.material.public_id, "approved_qty": item.requested_qty})

    approve_payload = ApproveRequestPayload(
        rmpm_warehouse_public_id=data["rmpm"].public_id,
        items=approve_items
    )
    req = svc.approve_request(req.id, approve_payload, approved_by=1, rmpm_warehouse_id=data["rmpm"].id)
    assert req.status == "APPROVED"

    # Check RMPM balance
    from app.domains.inventory.service import InventoryService
    inv = InventoryService(db)
    bal = inv.get_balance(material_id=data["mat"].id, warehouse_id=data["rmpm"].id)
    # 1000 receipt - 50 reservation = 950
    assert bal == Decimal("950.0000")

    # Check History & Notification
    from app.domains.requests.models import MaterialRequestHistory
    from app.domains.audit.models import Notification
    histories = db.query(MaterialRequestHistory).filter_by(request_id=req.id).all()
    assert len(histories) == 2  # CREATED, APPROVED
    
    notifs = db.query(Notification).filter_by(user_id=1).all()
    assert len(notifs) >= 1
    assert any(n.type == "REQUEST_APPROVED" for n in notifs)

def test_atomic_rollback_on_approval_failure(db):
    data = setup_master_data(db)
    svc = RequestService(db)
    today = datetime.date.today()
    
    # Give RMPM 0 kg of Potato (will fail reservation)
    # create request
    payload = CreateRequestPayload(
        request_date=today,
        ods_warehouse_public_id=data["ods"].public_id,
        skus=[
            RequestSKUInput(sku_public_id=data["sku1"].public_id, planned_production_qty=Decimal("10")),
        ]
    )
    req = svc.create_request(payload, created_by=1)
    
    from app.domains.requests.schemas import ApproveRequestPayload
    from app.core.errors import InsufficientInventoryError
    
    approve_payload = ApproveRequestPayload(
        rmpm_warehouse_public_id=data["rmpm"].public_id,
        items=[{"material_public_id": data["mat"].public_id, "approved_qty": Decimal("50")}]
    )
    
    # Use a savepoint to simulate a transaction failure
    savepoint = db.begin_nested()
    try:
        svc.approve_request(req.id, approve_payload, approved_by=1, rmpm_warehouse_id=data["rmpm"].id)
    except InsufficientInventoryError:
        savepoint.rollback()
    
    # Verify rollback: status is still SUBMITTED, no APPROVED history, no Notification
    from app.domains.requests.models import MaterialRequest, MaterialRequestHistory
    from app.domains.audit.models import Notification
    from app.domains.inventory.models import InventoryTransaction
    
    req_db = db.query(MaterialRequest).get(req.id)
    assert req_db.status == "SUBMITTED"
    
    histories = db.query(MaterialRequestHistory).filter_by(request_id=req.id, action="APPROVED").all()
    assert len(histories) == 0
    
    notifs = db.query(Notification).filter_by(type="REQUEST_APPROVED").all()
    assert len(notifs) == 0
    
    reservations = db.query(InventoryTransaction).filter_by(reference_type="MATERIAL_REQUEST", reference_id=req.id).all()
    assert len(reservations) == 0
