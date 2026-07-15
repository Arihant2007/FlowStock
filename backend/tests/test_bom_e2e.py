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

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(s1).to_excel(writer, sheet_name="Sheet1", header=False, index=False)
        pd.DataFrame(s2).to_excel(writer, sheet_name="Sheet2", header=False, index=False)
        pd.DataFrame(s3).to_excel(writer, sheet_name="Sheet3", header=False, index=False)
        pd.DataFrame(s4).to_excel(writer, sheet_name="Sheet4", header=False, index=False)

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
    preview = svc.preview_bom_upload(file_bytes, "bom.xlsx")

    # Verify Preview correctly reports:
    # - Empty worksheet skipped (no errors, but should process the rest)
    assert "Sheet4" in preview.empty_sheets

    # - Valid rows and errors
    assert preview.error_rows == 1 # Duplicate material code triggers an error row
    # Wait, the duplicate material code, unknown material, missing SKU code!

    # "Report block-level validation errors and continue parsing remaining SKU blocks instead of aborting the entire worksheet."
    # We should have global errors for Sheet2 (missing SKU code) but it shouldn't abort the rest!

    assert "FXC70010SL" in preview.new_skus
    assert "FXC70020PA" in preview.new_skus
    assert "UNKNOWN01" in preview.unknown_materials
    assert "FR000649E in FXC70040PA" in preview.duplicate_material_codes
    assert "FXC70020PA" in preview.duplicate_sku_codes

    # 3. Commit
    # The commit should raise ValidationError because of the unknown material and other issues.
    with pytest.raises(ValidationError):
        svc.commit_bom_upload(file_bytes, "bom.xlsx", created_by=1)

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
    svc.commit_bom_upload(valid_file_bytes, "bom_valid.xlsx", created_by=1)

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
