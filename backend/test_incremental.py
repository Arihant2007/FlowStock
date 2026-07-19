import asyncio
import os
import io
import sys
import pandas as pd
import datetime
sys.path.insert(0, '.')

from sqlalchemy import text
from app.infrastructure.database import SessionLocal, engine
from app.domains.master.service import MasterService
from app.domains.master.models import MaterialCategory, MaterialType, MaterialGroup, Material, SKU, BOMVersion, BOMItem, Warehouse

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
    
    # Ensure master data lookup values exist
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
        db.add(MaterialGroup(name='Others', created_by=1))
    db.commit()

def create_mock_boms():
    # BOM A: SKU-A with 100 materials (MAT-001 to MAT-100)
    data_a = [
        ["Product A", "SKU-A", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"]
    ]
    for i in range(1, 101):
        data_a.append([f"MAT-{i:03d}", f"Material {i}", 1.5, "KG"])
        
    df_a = pd.DataFrame(data_a)
    bom_a_bytes = io.BytesIO()
    df_a.to_excel(bom_a_bytes, index=False, header=False)
    bom_a_bytes = bom_a_bytes.getvalue()

    # BOM B: SKU-B with 95 existing materials (MAT-001 to MAT-095) + 5 new (NEW-001 to NEW-005)
    data_b = [
        ["Product B", "SKU-B", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"]
    ]
    for i in range(1, 96):
        data_b.append([f"MAT-{i:03d}", f"Material {i}", 2.0, "KG"])
    for i in range(1, 6):
        data_b.append([f"NEW-{i:03d}", f"New Material {i}", 3.0, "KG"])
        
    df_b = pd.DataFrame(data_b)
    bom_b_bytes = io.BytesIO()
    df_b.to_excel(bom_b_bytes, index=False, header=False)
    bom_b_bytes = bom_b_bytes.getvalue()
    
    return bom_a_bytes, bom_b_bytes

def run_test():
    db = SessionLocal()
    reset_db(db)
    
    bom_a_bytes, bom_b_bytes = create_mock_boms()
    svc = MasterService(db)
    
    print("--- 1. UPLOAD BOM A ---")
    mm_a_bytes = svc.extract_materials_from_bom(bom_a_bytes, 'bom_a.xlsx')
    mm_a_preview = svc.preview_material_upload(mm_a_bytes, 'mm_a.xlsx')
    if mm_a_preview.error_rows > 0:
        print("FAIL: BOM A Material Upload preview failed.")
        return
    svc.commit_material_upload(mm_a_bytes, 'mm_a.xlsx', created_by=1)
    db.commit()
    print("Materials after BOM A:", db.query(Material).count())
    
    bom_a_commit = svc.commit_bom_upload(bom_a_bytes, 'bom_a.xlsx', created_by=1)
    db.commit()
    print(f"SKUs after BOM A: {db.query(SKU).count()}")
    
    # Manually change category of MAT-001 to verify it is preserved
    mat1 = db.query(Material).filter_by(code='MAT-001').first()
    pm_cat = db.query(MaterialCategory).filter_by(name='Packaging Material').first()
    mat1.category_id = pm_cat.id
    db.commit()
    
    print("\n--- 2. UPLOAD BOM B ---")
    # If we extract materials for BOM B, it should only return the 5 new ones by default!
    mm_b_bytes = svc.extract_materials_from_bom(bom_b_bytes, 'bom_b.xlsx', only_unknown=True)
    
    # Let's inspect the generated material master
    df_mm_b = pd.read_excel(io.BytesIO(mm_b_bytes), engine='openpyxl')
    print("Materials extracted for BOM B (expect 5):", len(df_mm_b))
    if len(df_mm_b) != 5:
        print("FAIL: Material master template does not contain exactly 5 new materials.")
        return
        
    mm_b_preview = svc.preview_material_upload(mm_b_bytes, 'mm_b.xlsx')
    if mm_b_preview.error_rows > 0:
        print("FAIL: BOM B Material Upload preview failed.")
        return
        
    mm_b_commit = svc.commit_material_upload(mm_b_bytes, 'mm_b.xlsx', created_by=1)
    db.commit()
    print(f"Materials created for BOM B: {mm_b_commit['created']} (expect 5)")
    print("Total materials in DB:", db.query(Material).count())
    
    bom_b_commit = svc.commit_bom_upload(bom_b_bytes, 'bom_b.xlsx', created_by=1)
    db.commit()
    print(f"Total SKUs in DB: {db.query(SKU).count()} (expect 2)")
    
    # Verify classifications are preserved
    mat1_check = db.query(Material).filter_by(code='MAT-001').first()
    if mat1_check.category_id != pm_cat.id:
        print("FAIL: MAT-001 classification was not preserved.")
        return
    else:
        print("Classification for existing MAT-001 was preserved.")
        
    print("SUCCESS: Incremental BOM upload works flawlessly.")

if __name__ == "__main__":
    run_test()
