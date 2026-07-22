import asyncio
import datetime
import json
import uuid
import pandas as pd
from io import BytesIO
from decimal import Decimal
import requests

from app.main import app
from app.infrastructure.database import SessionLocal, engine
from app.domains.master.models import MaterialCategory, MaterialType, Material, Warehouse, SKU, BOMVersion, BOMItem
from app.domains.inventory.models import InventoryTransaction
from app.domains.requests.models import MaterialRequest
from app.domains.auth.models import User

# Use db directly for seeding
db = SessionLocal()

# We need the real auth tokens
BASE_URL = "http://localhost:8000/api/v1"
tokens = {}

def login(username, password):
    res = requests.post(f"{BASE_URL}/auth/login", json={"identifier": username, "password": password})
    if res.status_code == 200:
        return res.json()["data"]["access_token"]
    raise Exception(f"Failed to login {username}: {res.text}")

def setup_master_data():
    print("Setting up Master Data...")
    cat = db.query(MaterialCategory).first()
    if not cat:
        cat = MaterialCategory(name='Test Category', public_id=uuid.uuid4(), created_by=1)
        db.add(cat)
        
    typ = db.query(MaterialType).first()
    if not typ:
        typ = MaterialType(name='Test Type', public_id=uuid.uuid4(), created_by=1)
        db.add(typ)
    db.commit()

    materials = [
        ('RM-POTATO-01', 'Potato Extra', 'KG'),
        ('RM-OIL-01', 'Frying Oil', 'LTR'),
        ('PM-FILM-01', 'Printed Film 50g', 'KG'),
        ('PM-CARTON-01', 'Outer Carton', 'PCS'),
    ]
    for code, name, uom in materials:
        if not db.query(Material).filter_by(code=code).first():
            db.add(Material(code=code, name=name, category_id=cat.id, type_id=typ.id, uom=uom, created_by=1))
    db.commit()

    skus = [
        ('SKU-CHIPS-50G', 'Potato Chips 50g'),
        ('SKU-CHIPS-100G', 'Potato Chips 100g'),
    ]
    for code, name in skus:
        if not db.query(SKU).filter_by(code=code).first():
            db.add(SKU(code=code, name=name, public_id=uuid.uuid4(), created_by=1))
    db.commit()

    # Create BOM for 50G
    sku_50g = db.query(SKU).filter_by(code='SKU-CHIPS-50G').first()
    bom_50g = db.query(BOMVersion).filter_by(sku_id=sku_50g.id, version_number=1).first()
    if not bom_50g:
        bom_50g = BOMVersion(sku_id=sku_50g.id, version_number=1, is_active=True, created_by=1, public_id=uuid.uuid4())
        db.add(bom_50g)
        db.commit()
        db.add(BOMItem(bom_version_id=bom_50g.id, material_id=db.query(Material).filter_by(code='RM-POTATO-01').first().id, quantity_per_unit=Decimal("0.5"), created_by=1))
        db.add(BOMItem(bom_version_id=bom_50g.id, material_id=db.query(Material).filter_by(code='RM-OIL-01').first().id, quantity_per_unit=Decimal("0.1"), created_by=1))
        db.add(BOMItem(bom_version_id=bom_50g.id, material_id=db.query(Material).filter_by(code='PM-FILM-01').first().id, quantity_per_unit=Decimal("0.02"), created_by=1))
        db.add(BOMItem(bom_version_id=bom_50g.id, material_id=db.query(Material).filter_by(code='PM-CARTON-01').first().id, quantity_per_unit=Decimal("0.01"), created_by=1))
    
    # Create BOM for 100G
    sku_100g = db.query(SKU).filter_by(code='SKU-CHIPS-100G').first()
    bom_100g = db.query(BOMVersion).filter_by(sku_id=sku_100g.id, version_number=1).first()
    if not bom_100g:
        bom_100g = BOMVersion(sku_id=sku_100g.id, version_number=1, is_active=True, created_by=1, public_id=uuid.uuid4())
        db.add(bom_100g)
        db.commit()
        db.add(BOMItem(bom_version_id=bom_100g.id, material_id=db.query(Material).filter_by(code='RM-POTATO-01').first().id, quantity_per_unit=Decimal("0.9"), created_by=1))
        db.add(BOMItem(bom_version_id=bom_100g.id, material_id=db.query(Material).filter_by(code='RM-OIL-01').first().id, quantity_per_unit=Decimal("0.18"), created_by=1))
        db.add(BOMItem(bom_version_id=bom_100g.id, material_id=db.query(Material).filter_by(code='PM-FILM-01').first().id, quantity_per_unit=Decimal("0.03"), created_by=1))
    db.commit()
    print("Master Data Set Up Completed.")

def run_simulation():
    tokens['admin'] = login("admin", "Admin@12345")
    tokens['ods_op'] = login("ods_op", "OdsOp@12345")
    tokens['rmpm_op'] = login("rmpm_op", "Rmpm@12345")

    setup_master_data()

    print("\n--- 1. UPLOAD RMPM SNAPSHOT (Warehouse Init) ---")
    headers = {"Authorization": f"Bearer {tokens['rmpm_op']}"}
    df_rmpm = pd.DataFrame([
        {"Material Code": "RM-POTATO-01", "Quantity": 1000},
        {"Material Code": "RM-OIL-01", "Quantity": 500},
        {"Material Code": "PM-FILM-01", "Quantity": 100},
        {"Material Code": "PM-CARTON-01", "Quantity": 20}, # Low stock scenario
    ])
    excel_file = BytesIO()
    df_rmpm.to_excel(excel_file, index=False)
    excel_file.seek(0)
    files = {"file": ("rmpm_snapshot.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/inventory/upload/preview", headers=headers, files=files)
    preview_data = res.json()
    cache_id = preview_data["data"]["cache_id"]
    res = requests.post(f"{BASE_URL}/inventory/upload/commit", headers=headers, json={"cache_id": cache_id})
    print(f"RMPM Commit Status: {res.status_code}")

    print("\n--- 2. UPLOAD ODS PLAN (Multiple SKUs) ---")
    headers_ods = {"Authorization": f"Bearer {tokens['ods_op']}"}
    # Business Date must be tomorrow to avoid "same date" collisions in test
    business_date = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    df_ods = pd.DataFrame([
        {"Business Date": business_date, "SKU": "SKU-CHIPS-50G", "FG Quantity": 5000, "Material": "RM-POTATO-01", "Remaining Quantity": 50},
        {"Business Date": business_date, "SKU": "SKU-CHIPS-50G", "FG Quantity": 5000, "Material": "RM-OIL-01", "Remaining Quantity": 10},
        {"Business Date": business_date, "SKU": "SKU-CHIPS-50G", "FG Quantity": 5000, "Material": "PM-FILM-01", "Remaining Quantity": 0},
        {"Business Date": business_date, "SKU": "SKU-CHIPS-50G", "FG Quantity": 5000, "Material": "PM-CARTON-01", "Remaining Quantity": 0},
        
        {"Business Date": business_date, "SKU": "SKU-CHIPS-100G", "FG Quantity": 1000, "Material": "RM-POTATO-01", "Remaining Quantity": 0},
        {"Business Date": business_date, "SKU": "SKU-CHIPS-100G", "FG Quantity": 1000, "Material": "RM-OIL-01", "Remaining Quantity": 0},
        {"Business Date": business_date, "SKU": "SKU-CHIPS-100G", "FG Quantity": 1000, "Material": "PM-FILM-01", "Remaining Quantity": 0},
    ])
    excel_file = BytesIO()
    df_ods.to_excel(excel_file, index=False)
    excel_file.seek(0)
    files = {"file": ("ods_plan.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers_ods, files=files)
    preview_data = res.json()
    if res.status_code != 200:
        print("ODS Preview Failed:", res.text)
        return
    cache_id = preview_data["data"]["cache_id"]
    res = requests.post(f"{BASE_URL}/requests/upload/commit", headers=headers_ods, json={"cache_id": cache_id})
    print(f"ODS Commit Status: {res.status_code}")
    req_public_id = res.json()["data"]["public_id"]
    
    print("\n--- 3. VERIFY DUPLICATE UPLOAD FAILS ---")
    excel_file.seek(0)
    files = {"file": ("ods_plan.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers_ods, files=files)
    print(f"Duplicate Upload Status (Expect 400): {res.status_code}, {res.text[:100]}")

    print("\n--- 4. GET REQUEST DETAILS ---")
    res = requests.get(f"{BASE_URL}/requests/{req_public_id}", headers=headers_ods)
    req_data = res.json()["data"]
    print("Request Status:", req_data["status"])
    
    print("\n--- 5. PARTIAL APPROVAL (Low Stock Scenario) ---")
    items_to_approve = []
    for sku in req_data["skus"]:
        for item in sku["items"]:
            # Intentionally approve less than requested for cartons because of low stock
            if "CARTON" in item["material"]["code"]:
                approved_qty = 20 # Only 20 in stock!
            else:
                approved_qty = item["requested_qty"]
            items_to_approve.append({"item_id": item["public_id"], "approved_qty": float(approved_qty)})
    
    res = requests.post(f"{BASE_URL}/requests/{req_public_id}/approve", headers=headers, json={"items": items_to_approve})
    print("Approval Status:", res.status_code)
    
    print("\n--- 6. DISPATCH ---")
    items_to_dispatch = [{"item_id": i["item_id"], "dispatched_qty": i["approved_qty"]} for i in items_to_approve]
    res = requests.post(f"{BASE_URL}/requests/{req_public_id}/dispatch", headers=headers, json={"items": items_to_dispatch})
    print("Dispatch Status:", res.status_code)
    
    print("\n--- 7. RECEIPT (With Loss) ---")
    items_to_receive = []
    for i in items_to_dispatch:
        # Simulate loss in transit for POTATO
        rcv = i["dispatched_qty"]
        items_to_receive.append({"item_id": i["item_id"], "received_qty": rcv})
        
    res = requests.post(f"{BASE_URL}/requests/{req_public_id}/receive", headers=headers_ods, json={"items": items_to_receive})
    print("Receive Status:", res.status_code)

    print("\n--- 8. VERIFY REPORTS ---")
    res = requests.get(f"{BASE_URL}/reports/inventory", headers=headers)
    print("Inventory Report length:", len(res.json()["data"]))
    
    print("SIMULATION COMPLETED SUCCESSFULLY")

if __name__ == "__main__":
    run_simulation()
