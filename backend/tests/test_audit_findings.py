import datetime
from decimal import Decimal

from app.domains.inventory.models import InventorySnapshot, InventoryTransaction
from app.domains.inventory.service import InventoryService
from app.domains.master.models import (
    SKU,
    BOMItem,
    BOMVersion,
    Material,
    MaterialCategory,
    MaterialType,
    Warehouse,
)
from app.domains.requests.schemas import CreateRequestPayload, RequestSKUInput
from app.domains.requests.service import RequestService


def setup_master_data(db):
    import uuid
    cat = MaterialCategory(name="Cat", public_id=uuid.uuid4())
    mtype = MaterialType(name="RM", public_id=uuid.uuid4())
    db.add_all([cat, mtype])
    db.flush()

    mat_potato = Material(code="POTATO", name="Potato", uom="KG", category_id=cat.id, type_id=mtype.id, created_by=1, public_id=uuid.uuid4())
    mat_salt = Material(code="SALT", name="Salt", uom="KG", category_id=cat.id, type_id=mtype.id, created_by=1, public_id=uuid.uuid4())
    db.add_all([mat_potato, mat_salt])
    db.flush()

    sku_a = SKU(code="SKU-A", name="SKU A", created_by=1, public_id=uuid.uuid4())
    sku_b = SKU(code="SKU-B", name="SKU B", created_by=1, public_id=uuid.uuid4())
    db.add_all([sku_a, sku_b])
    db.flush()

    bom_a = BOMVersion(sku_id=sku_a.id, version_number=1, is_active=True, created_by=1)
    db.add(bom_a)
    db.flush()
    db.add_all([
        BOMItem(bom_version_id=bom_a.id, material_id=mat_potato.id, quantity_per_unit=Decimal("10.0"), created_by=1),
        BOMItem(bom_version_id=bom_a.id, material_id=mat_salt.id, quantity_per_unit=Decimal("1.0"), created_by=1),
    ])

    bom_b = BOMVersion(sku_id=sku_b.id, version_number=1, is_active=True, created_by=1)
    db.add(bom_b)
    db.flush()
    db.add_all([
        BOMItem(bom_version_id=bom_b.id, material_id=mat_potato.id, quantity_per_unit=Decimal("5.0"), created_by=1),
    ])

    ods = Warehouse(name="ODS", type="ODS", created_by=1, public_id=uuid.uuid4())
    rmpm = Warehouse(name="RMPM", type="RMPM", created_by=1, public_id=uuid.uuid4())
    db.add_all([ods, rmpm])
    db.flush()

    return {
        "mat_potato": mat_potato,
        "mat_salt": mat_salt,
        "sku_a": sku_a,
        "sku_b": sku_b,
        "ods": ods,
        "rmpm": rmpm,
    }


def test_issue_1_aggregation(db):
    data = setup_master_data(db)

    db.add(InventoryTransaction(
        material_id=data["mat_potato"].id,
        destination_warehouse_id=data["ods"].id,
        transaction_type="RECEIPT",
        quantity=Decimal("100"),
        created_by=1
    ))
    db.flush()

    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    today = datetime.date.today()
    db.add(InventorySnapshot(
        material_id=data["mat_potato"].id,
        warehouse_id=data["ods"].id,
        snapshot_date=yesterday,
        closing_balance=Decimal("100"),
        created_by=1
    ))
    db.flush()

    svc = RequestService(db)
    payload = CreateRequestPayload(
        request_date=today,
        ods_warehouse_public_id=data["ods"].public_id,
        skus=[
            RequestSKUInput(sku_public_id=data["sku_a"].public_id, planned_production_qty=Decimal("10")),
            RequestSKUInput(sku_public_id=data["sku_b"].public_id, planned_production_qty=Decimal("10")),
        ]
    )

    req = svc.create_request(payload, created_by=1)

    potato_net = sum(item.requested_qty for sku in req.skus for item in sku.items if item.material_id == data["mat_potato"].id)

    print("\n--- Issue 1 ---")
    print("Expected Net Potato: 50")
    print(f"Actual Net Potato: {potato_net}")
    assert potato_net == 50, "The backend failed to aggregate the duplicate material correctly."

def test_issue_2_double_deduction(db):
    data = setup_master_data(db)

    db.add(InventoryTransaction(
        material_id=data["mat_potato"].id,
        destination_warehouse_id=data["rmpm"].id,
        transaction_type="RECEIPT",
        quantity=Decimal("100"),
        created_by=1
    ))
    db.flush()

    inv_svc = InventoryService(db)
    balance_before = inv_svc.get_balance(data["mat_potato"].id, data["rmpm"].id)

    inv_svc.reserve(
        material_id=data["mat_potato"].id,
        source_warehouse_id=data["rmpm"].id,
        quantity=Decimal("20"),
        reference_type="TEST",
        reference_id=1,
        reserved_by=1
    )
    balance_after_reserve = inv_svc.get_balance(data["mat_potato"].id, data["rmpm"].id)

    inv_svc.dispatch_transfer(
        material_id=data["mat_potato"].id,
        source_warehouse_id=data["rmpm"].id,
        quantity=Decimal("20"),
        reference_type="TEST",
        reference_id=1,
        dispatched_by=1
    )
    balance_after_dispatch = inv_svc.get_balance(data["mat_potato"].id, data["rmpm"].id)

    print("\n--- Issue 2 ---")
    print(f"Balance before: {balance_before}")
    print(f"Balance after reserve: {balance_after_reserve}")
    print(f"Balance after dispatch (Expected: 80, Actual: {balance_after_dispatch})")
    assert balance_after_dispatch != 80, "If this assertion fails, the bug is already fixed!"

def test_issue_3_snapshot_date(db):
    data = setup_master_data(db)

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    db.add(InventorySnapshot(
        material_id=data["mat_potato"].id,
        warehouse_id=data["ods"].id,
        snapshot_date=yesterday,
        closing_balance=Decimal("100"),
        created_by=1
    ))
    db.flush()

    svc = RequestService(db)
    payload = CreateRequestPayload(
        request_date=today,
        ods_warehouse_public_id=data["ods"].public_id,
        skus=[
            RequestSKUInput(sku_public_id=data["sku_a"].public_id, planned_production_qty=Decimal("10")),
        ]
    )

    print("\n--- Issue 3 ---")
    try:
        svc.create_request(payload, created_by=1)
        print("Success! Created request.")
    except Exception as e:
        print(f"Failed to create request: {e}")
        assert "is missing" in str(e)
