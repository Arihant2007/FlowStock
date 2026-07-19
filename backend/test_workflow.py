import asyncio
import os
import io
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.infrastructure.database import SessionLocal, engine
from app.domains.master.service import MasterService
from app.domains.master.models import MaterialCategory, MaterialType, MaterialGroup, Material, SKU, BOMVersion, BOMItem, Warehouse
from app.domains.inventory.models import InventoryTransaction, InventorySnapshot
from app.domains.requests.models import MaterialRequest, MaterialRequestSKU, MaterialRequestItem
import datetime

def reset_db(db):
    db.execute(text("DELETE FROM inventory_transactions"))
    db.execute(text("DELETE FROM inventory_snapshots"))
    db.execute(text("DELETE FROM material_request_items"))
    db.execute(text("DELETE FROM material_request_skus"))
    db.execute(text("DELETE FROM material_requests"))
    db.execute(text("DELETE FROM bom_items"))
    db.execute(text("DELETE FROM bom_versions"))
    db.execute(text("DELETE FROM materials"))
    db.execute(text("DELETE FROM material_groups"))
    db.execute(text("DELETE FROM skus"))
    db.commit()
    # ensure categories and types exist
    cat = db.query(MaterialCategory).filter_by(name='Raw Material').first()
    if not cat:
        db.add(MaterialCategory(name='Raw Material', created_by=1))
        db.add(MaterialCategory(name='Packaging Material', created_by=1))
        db.add(MaterialCategory(name='Others', created_by=1))
    
    typ = db.query(MaterialType).filter_by(name='RM').first()
    if not typ:
        db.add(MaterialType(name='RM', created_by=1))
        db.add(MaterialType(name='PM', created_by=1))
    
    grp = db.query(MaterialGroup).filter_by(name='Ingredients').first()
    if not grp:
        db.add(MaterialGroup(name='Ingredients', created_by=1))
        db.add(MaterialGroup(name='Laminates', created_by=1))
        db.add(MaterialGroup(name='Films', created_by=1))
        db.add(MaterialGroup(name='Cartons', created_by=1))
        db.add(MaterialGroup(name='Pouches', created_by=1))
        db.add(MaterialGroup(name='Labels', created_by=1))
        db.add(MaterialGroup(name='Others', created_by=1))
        
    db.commit()
    
    wh_ods = db.query(Warehouse).filter_by(type='ODS').first()
    if not wh_ods:
        wh_ods = Warehouse(name='ODS Warehouse', type='ODS', created_by=1)
        db.add(wh_ods)
    wh_rmpm = db.query(Warehouse).filter_by(type='RMPM').first()
    if not wh_rmpm:
        wh_rmpm = Warehouse(name='RMPM Warehouse', type='RMPM', created_by=1)
        db.add(wh_rmpm)
    db.commit()

def run_test():
    db = SessionLocal()
    reset_db(db)
    
    print("Database reset.")
    
    with open('Skus_Bom.xlsx', 'rb') as f:
        bom_bytes = f.read()
    
    svc = MasterService(db)
    
    # 1. Preview BOM
    print("\n--- 1. PREVIEW BOM ---")
    bom_preview = svc.preview_bom_upload(bom_bytes, 'Skus_Bom.xlsx')
    print(f"Unknown Materials: {len(bom_preview.unknown_materials)}")
    
    # 2. Extract Materials
    print("\n--- 2. EXTRACT MATERIALS ---")
    mm_bytes = svc.extract_materials_from_bom(bom_bytes, 'Skus_Bom.xlsx')
    
    # 3. Preview Material Master
    print("\n--- 3. PREVIEW MATERIAL MASTER ---")
    mm_preview = svc.preview_material_upload(mm_bytes, 'extracted.xlsx')
    print(f"Material Upload Valid Rows: {mm_preview.valid_rows}")
    print(f"Material Upload Error Rows: {mm_preview.error_rows}")
    if mm_preview.error_rows > 0:
        for r in mm_preview.rows:
            if r.status == 'error':
                print(f"Row {r.row_number} error: {r.message}")
        print("FAIL: Validation errors during material master preview.")
        return
        
    # 4. Commit Material Master
    print("\n--- 4. COMMIT MATERIAL MASTER ---")
    mm_commit = svc.commit_material_upload(mm_bytes, 'extracted.xlsx', created_by=1)
    db.commit()
    print(f"Materials created: {mm_commit['created']}")
    
    # 5. Preview BOM Again
    print("\n--- 5. PREVIEW BOM AGAIN ---")
    bom_preview_2 = svc.preview_bom_upload(bom_bytes, 'Skus_Bom.xlsx')
    print(f"Unknown Materials: {len(bom_preview_2.unknown_materials)}")
    if len(bom_preview_2.unknown_materials) > 0:
        print("FAIL: Unknown materials still exist after Material Master upload.")
        return
        
    # 6. Commit BOM
    print("\n--- 6. COMMIT BOM ---")
    bom_commit = svc.commit_bom_upload(bom_bytes, 'Skus_Bom.xlsx', created_by=1)
    db.commit()
    print(f"SKUs updated/created: {bom_commit['skus_updated']}")
    print(f"BOM Items created: {bom_commit['items_created']}")
    
    # 7. Create ODS Request
    print("\n--- 7. CREATE ODS REQUEST ---")
    from app.domains.requests.service import RequestService
    from app.domains.requests.schemas import CreateRequestPayload, RequestSKUInput
    
    req_svc = RequestService(db)
    wh_ods = db.query(Warehouse).filter_by(type='ODS').first()
    
    sku = db.query(SKU).first()
    if not sku:
        print("FAIL: No SKU created.")
        return
        
    # We need a snapshot for the ODS Warehouse to create a request
    materials = db.query(Material).all()
    if materials:
        for m in materials:
            db.add(InventorySnapshot(material_id=m.id, warehouse_id=wh_ods.id, snapshot_date=datetime.date.today() - datetime.timedelta(days=1), closing_balance=0, created_by=1))
        db.commit()
        
    req_payload = CreateRequestPayload(
        request_date=datetime.date.today(),
        notes='Test request',
        ods_warehouse_public_id=wh_ods.public_id,
        skus=[RequestSKUInput(sku_public_id=sku.public_id, planned_production_qty=5.0)]
    )
    
    try:
        req_res = req_svc.create_request(req_payload, created_by=1)
        db.commit()
        print(f"ODS Request created successfully with {len(req_res.skus)} SKU lines.")
        print("SUCCESS: Workflow completed successfully!")
    except Exception as e:
        print(f"FAIL: Failed to create ODS request: {e}")

if __name__ == "__main__":
    run_test()
