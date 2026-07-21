import uuid
from decimal import Decimal
from io import BytesIO

import pandas as pd
import pytest
from sqlalchemy import select

from app.core.errors import ValidationError
from app.domains.inventory.models import InventorySnapshot
from app.domains.master.models import (
    SKU,
    Material,
    MaterialCategory,
    MaterialType,
    Warehouse,
)
from app.domains.master.service import MasterService
from app.domains.requests.schemas import CreateRequestPayload, RequestSKUInput
from app.domains.requests.service import RequestService


def create_mock_bom_excel() -> bytes:
    # Sheet 1 has MULTIPLE SKU BLOCKS and blank rows
    s1 = [
        ["FCC 10 RS", "FXC70010SL", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3138.41", "KG"],
        ["FR001373", "IODISED SALT - SUPER FINE", "16.061", "KG"],
        ["", "", "", ""], # Blank rows for realism
        ["", "", "", ""],
        ["FCC 20 RS", "FXC70020PA", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3138.41", "KG"],
        ["FPSX02900", "LAM - PC FC CHILLI SPRINKLED", "115.122", "KG"],
        ["FCC 50 RS", "FXC70051PB", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "2000", "KG"],
    ]

    # Sheet 2 has errors (missing SKU code, unknown material, duplicate material code)
    s2 = [
        ["FCC 30 RS", "", "", ""], # Missing SKU Code (Invalid Block)
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3138.41", "KG"],
        ["", "", "", ""],
        ["FCC 40 RS", "FXC70040PA", "", ""], # Valid block with unknown material & duplicate code
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "100", "KG"],
        ["FR000649E", "POTATO-EXTERNAL", "50", "KG"], # duplicate material code
        ["UNKNOWN01", "Some unknown mat", "10", "KG"], # unknown material
    ]

    # Sheet 3 has a duplicate SKU Code (another block for FCC 20 RS)
    s3 = [
        ["FCC 20 RS", "FXC70020PA", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR001373", "IODISED SALT - SUPER FINE", "50", "KG"],
    ]

    # Sheet 4 is entirely empty
    s4: list[list[str]] = []

    # Sheet 5: No repeated headers for subsequent blocks (Regression test)
    s5 = [
        ["FCC 10 RS", "FXC70010SL", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3138.41", "KG"],
        ["FR001373", "IODISED SALT - SUPER FINE", "16.061", "KG"],
        ["FCC 20 RS", "FXC70020PA", "", ""],
        ["FR000649E", "POTATO-EXTERNAL", "3138.41", "KG"],
        ["FPSX02900", "LAM - PC FC CHILLI SPRINKLED", "115.122", "KG"],
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(s1).to_excel(writer, sheet_name="Sheet1", header=False, index=False)
        pd.DataFrame(s2).to_excel(writer, sheet_name="Sheet2", header=False, index=False)
        pd.DataFrame(s3).to_excel(writer, sheet_name="Sheet3", header=False, index=False)
        pd.DataFrame(s4).to_excel(writer, sheet_name="Sheet4", header=False, index=False)
        pd.DataFrame(s5).to_excel(writer, sheet_name="Sheet5", header=False, index=False)

    return output.getvalue()

def test_bom_upload_parser(db):
    svc = MasterService(db)

    # 1. Setup master materials so they aren't "Unknown"
    cat = MaterialCategory(name="Raw Material", public_id=uuid.uuid4(), created_by=1)
    typ = MaterialType(name="Ingredient", public_id=uuid.uuid4(), created_by=1)
    db.add(cat)
    db.add(typ)
    db.flush()

    mat1 = Material(code="FR000649E", name="POTATO-EXTERNAL", category_id=cat.id, type_id=typ.id, uom="KG", created_by=1)
    mat2 = Material(code="FR001373", name="IODISED SALT - SUPER FINE", category_id=cat.id, type_id=typ.id, uom="KG", created_by=1)
    mat3 = Material(code="FPSX02900", name="LAM - PC FC CHILLI SPRINKLED", category_id=cat.id, type_id=typ.id, uom="KG", created_by=1)
    db.add_all([mat1, mat2, mat3])
    db.flush()
    db.commit()

    # 2. Preview
    file_bytes = create_mock_bom_excel()
    preview = svc.preview_bom_upload(file_bytes, "bom.xlsx", session_id=None, current_user_id=1)

    # Verify Preview correctly reports:
    # - Empty worksheet skipped (no errors, but should process the rest)
    assert "Sheet4" in preview.empty_sheets

    # - Valid rows and errors
    assert preview.error_rows == 6 # 1 from s2, 4 from s5 (duplicate materials for the same SKUs in s1), 1 unknown material
    # Wait, the duplicate material code, unknown material, missing SKU code!

    # We should NOT have global errors for Sheet2 (missing SKU code) because it falls back to Name.
    assert len(preview.errors) == 0

    assert "FXC70010SL" in preview.new_skus
    assert "FXC70020PA" in preview.new_skus
    assert "FXC70051PB" in preview.new_skus
    assert "FCC 30 RS" in preview.new_skus  # This validates the fallback logic
    assert "UNKNOWN01" in preview.unknown_materials
    assert "FR000649E in FXC70040PA" in preview.duplicate_material_codes
    assert "FXC70020PA" in preview.duplicate_sku_codes

    # Ensure material counts per SKU are correct
    # Sheet1 has 3 SKUs. 1st has 2 items, 2nd has 2 items, 3rd has 1 item.
    sheet1_rows = [r for r in preview.rows if r.sheet_name == "Sheet1"]
    assert len(sheet1_rows) == 5
    sku1_items = [r for r in sheet1_rows if r.sku_code == "FXC70010SL"]
    sku2_items = [r for r in sheet1_rows if r.sku_code == "FXC70020PA"]
    sku3_items = [r for r in sheet1_rows if r.sku_code == "FXC70051PB"]
    assert len(sku1_items) == 2
    assert len(sku2_items) == 2
    assert len(sku3_items) == 1

    # Ensure Sheet5 works even without repeated headers
    sheet5_rows = [r for r in preview.rows if r.sheet_name == "Sheet5"]
    assert len(sheet5_rows) == 4
    sku1_items_s5 = [r for r in sheet5_rows if r.sku_code == "FXC70010SL"]
    sku2_items_s5 = [r for r in sheet5_rows if r.sku_code == "FXC70020PA"]
    assert len(sku1_items_s5) == 2
    assert len(sku2_items_s5) == 2

    # 3. Commit
    # The commit should raise ValidationError because of the unknown material and other issues.
    with pytest.raises(ValidationError):
        svc.commit_bom_upload(session_id=preview.session_id, current_user_id=1)

    # Now let's create a valid file to verify Request creation
    valid_s1 = [
        ["FCC 10 RS", "FXC70010SL", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3000", "KG"],
        ["", "", "", ""],
        ["FCC 20 RS", "FXC70020PA", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "2000", "KG"],
        ["FR001373", "IODISED SALT - SUPER FINE", "100", "KG"],
    ]
    output2 = BytesIO()
    with pd.ExcelWriter(output2, engine='openpyxl') as writer:
        pd.DataFrame(valid_s1).to_excel(writer, header=False, index=False)

    valid_file_bytes = output2.getvalue()
    valid_preview = svc.preview_bom_upload(valid_file_bytes, "bom_valid.xlsx", session_id=None, current_user_id=1)
    svc.commit_bom_upload(session_id=valid_preview.session_id, current_user_id=1)

    # 4. Verify request creation:
    # Set up ODS Warehouse and Inventory for Request creation
    wh_ods = Warehouse(name="ODS-Test", type="ODS", public_id=uuid.uuid4(), created_by=1)
    db.add(wh_ods)
    db.flush()

    # Add inventory snapshot for yesterday to satisfy the validation
    from datetime import date, timedelta
    yesterday = date.today() - timedelta(days=1)
    snapshot = InventorySnapshot(material_id=mat1.id, warehouse_id=wh_ods.id, snapshot_date=yesterday, closing_balance=Decimal("10000.0000"), created_by=1)
    db.add(snapshot)

    # Let's say we have 10,000 KG of POTATO in ODS
    from app.domains.inventory.models import InventoryTransaction
    ledger = InventoryTransaction(
        material_id=mat1.id,
        destination_warehouse_id=wh_ods.id,
        transaction_type="RECEIPT",
        quantity=Decimal("10000.0000"),
        reference_type="TEST",
        reference_id=1,
        created_by=1
    )
    db.add(ledger)
    db.flush()

    req_svc = RequestService(db)
    sku1 = db.scalar(select(SKU).where(SKU.code == "FXC70010SL"))
    sku2 = db.scalar(select(SKU).where(SKU.code == "FXC70020PA"))

    # Create request
    payload = CreateRequestPayload(
        request_date=date.today(),
        notes="Test Request",
        ods_warehouse_public_id=str(wh_ods.public_id),
        skus=[
            RequestSKUInput(sku_public_id=str(sku1.public_id), planned_production_qty=Decimal("2.0")), # Needs 6000 potato
            RequestSKUInput(sku_public_id=str(sku2.public_id), planned_production_qty=Decimal("1.5"))  # Needs 3000 potato, 150 salt
        ]
    )

    req = req_svc.create_request(payload, created_by=1)

    # Total potato needed = 6000 + 3000 = 9000. ODS has 10000.
    # Total salt needed = 150. ODS has 0.
    # Check that requirements are correctly calculated across SKUs.
    assert len(req.skus) == 2

    items = []
    for s in req.skus:
        for i in s.items:
            items.append((i.material_id, i.gross_required_qty, i.remaining_from_previous_day, i.requested_qty))

    # Verify POTATO for SKU 1
    p1 = next(i for i in items if i[0] == mat1.id and i[1] == Decimal("6000.0000"))
    assert p1[2] == Decimal("6000.0000") # Remaining used
    assert p1[3] == Decimal("0.0000") # Net requested

    # Verify POTATO for SKU 2
    p2 = next(i for i in items if i[0] == mat1.id and i[1] == Decimal("3000.0000"))
    assert p2[2] == Decimal("3000.0000") # Remaining used (10000 - 6000 = 4000 left)
    assert p2[3] == Decimal("0.0000") # Net requested

    # Verify SALT for SKU 2
    s2 = next(i for i in items if i[0] == mat2.id and i[1] == Decimal("150.0000"))
    assert s2[2] == Decimal("0.0000")
    assert s2[3] == Decimal("150.0000")

def test_archive_material_constraint(db):
    svc = MasterService(db)
    # Create materials and SKU
    cat = MaterialCategory(name="Raw Material 2", public_id=uuid.uuid4(), created_by=1)
    typ = MaterialType(name="Ingredient 2", public_id=uuid.uuid4(), created_by=1)
    db.add(cat)
    db.add(typ)
    db.flush()

    mat = Material(code="FR001234", name="TEST MATERIAL", category_id=cat.id, type_id=typ.id, uom="KG", created_by=1)
    db.add(mat)
    db.flush()

    # Upload BOM to use this material
    s1 = [
        ["FCC 100 RS", "FXC70100SL", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR001234", "TEST MATERIAL", "100", "KG"],
    ]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(s1).to_excel(writer, header=False, index=False)
    file_bytes = output.getvalue()
    
    preview = svc.preview_bom_upload(file_bytes, "bom.xlsx", session_id=None, current_user_id=1)
    svc.commit_bom_upload(session_id=preview.session_id, current_user_id=1)

    # Attempt to archive material -> should fail
    with pytest.raises(ValidationError, match="Cannot archive material. It is actively referenced in one or more active BOMs."):
        svc.archive_material(str(mat.public_id), deleted_by=1)

    # ---------------------------------------------------------
    # Test Dashboard and History using the populated data
    # ---------------------------------------------------------
    stats = svc.get_dashboard_stats()
    assert stats["total_materials"] > 0
    assert stats["total_skus"] > 0
    assert stats["total_bom_versions"] > 0
    assert stats["total_bom_items"] > 0
    assert stats["last_import_at"] is not None

    history = svc.list_bom_sessions()
    assert len(history) > 0
    
    # Check that commit summary is populated
    committed = [h for h in history if h.status == "COMMITTED"]
    assert len(committed) > 0
    assert committed[0].import_results is not None
    assert "skus_created" in committed[0].import_results
    assert "duration_seconds" in committed[0].import_results
