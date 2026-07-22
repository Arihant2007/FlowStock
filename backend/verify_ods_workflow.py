import asyncio
import datetime
import json
import uuid
import pandas as pd
from io import BytesIO
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.infrastructure.database import SessionLocal, engine
from app.domains.master.models import MaterialCategory, MaterialType, Material, Warehouse, SKU, BOMVersion, BOMItem
from app.domains.inventory.models import InventoryTransaction, InventorySnapshot
from app.domains.requests.models import MaterialRequest
from app.domains.auth.dependencies import get_current_user

# Custom JSON encoder
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

db = SessionLocal()

# Setup test user and roles
class MockPermissionObj:
    def __init__(self, code):
        self.code = code

class MockRolePermission:
    def __init__(self, code):
        self.permission = MockPermissionObj(code)

class MockRole:
    name = "admin"
    permissions = [
        MockRolePermission("master:write"),
        MockRolePermission("master:read"),
        MockRolePermission("inventory:upload"),
        MockRolePermission("inventory:read"),
        MockRolePermission("inventory:adjust"),
        MockRolePermission("requests:write"),
        MockRolePermission("requests:read"),
        MockRolePermission("requests:create"),
        MockRolePermission("requests:approve"),
        MockRolePermission("reports:read"),
    ]

class MockUser:
    id = 1
    public_id = uuid.uuid4()
    username = "admin"
    email = "admin@itc.in"
    full_name = "Admin"
    role_id = 1
    role = MockRole()
    warehouse_id = None
    is_active = True
    created_at = datetime.datetime.now()
    updated_at = None

def override_get_current_user():
    from app.domains.auth.models import User
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        return MockUser()
    return admin

app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(app)
headers = {}

def get_inventory(warehouse_type, mat_code):
    db.commit()
    wh = db.query(Warehouse).filter_by(type=warehouse_type).first()
    mat = db.query(Material).filter_by(code=mat_code).first()
    print(f"DEBUG get_inventory: wh={wh.name if wh else None}, mat={mat.code if mat else None}")
    if not wh or not mat:
        return 0
    from app.domains.inventory.service import InventoryService
    balance = InventoryService(db).get_balance(mat.id, wh.id)
    print(f"DEBUG balance returned: {balance}")
    return float(balance)

def print_section(title):
    print(f"\n{'-'*80}")
    print(f"{title.upper()}")
    print(f"{'-'*80}")

def run_workflow():
    print_section("0. Initializing Master Data (BOM & SKUs)")
    cat = db.query(MaterialCategory).first()
    if not cat:
        cat = MaterialCategory(name='Test Category', public_id=uuid.uuid4(), created_by=1)
        db.add(cat)
    typ = db.query(MaterialType).first()
    if not typ:
        typ = MaterialType(name='Test Type', public_id=uuid.uuid4(), created_by=1)
        db.add(typ)
    db.commit()

    wh_ods = db.query(Warehouse).filter_by(type='ODS').first()
    if not wh_ods:
        wh_ods = Warehouse(name='ODS Warehouse', type='ODS', public_id=uuid.uuid4(), created_by=1)
        db.add(wh_ods)
    wh_rmpm = db.query(Warehouse).filter_by(type='RMPM').first()
    if not wh_rmpm:
        wh_rmpm = Warehouse(name='RMPM Warehouse', type='RMPM', public_id=uuid.uuid4(), created_by=1)
        db.add(wh_rmpm)
    db.commit()

    materials = ['FR000649E', 'FR001373']
    for code in materials:
        if not db.query(Material).filter_by(code=code).first():
            db.add(Material(code=code, name=code, category_id=cat.id, type_id=typ.id, uom='KG', created_by=1))
    db.commit()
    
    sku_code = 'TEST_SKU_ODS_123'
    sku = db.query(SKU).filter_by(code=sku_code).first()
    if not sku:
        sku = SKU(code=sku_code, name='Test SKU', public_id=uuid.uuid4(), created_by=1)
        db.add(sku)
        db.commit()
    else:
        sku.deleted_at = None
        db.commit()
        
    bom = db.query(BOMVersion).filter_by(sku_id=sku.id, version_number=1).first()
    if not bom:
        bom = BOMVersion(sku_id=sku.id, version_number=1, is_active=True, created_by=1, public_id=uuid.uuid4())
        db.add(bom)
        db.commit()
    
    mat = db.query(Material).filter_by(code='FR000649E').first()
    bom_item = db.query(BOMItem).filter_by(bom_version_id=bom.id, material_id=mat.id).first()
    if not bom_item:
        db.add(BOMItem(bom_version_id=bom.id, material_id=mat.id, quantity_per_unit=Decimal("0.5"), created_by=1))
        db.commit()

    # 1. Fetch SKUs and setup test data
    skus_res = client.get('/api/v1/master/skus', headers=headers)
    skus_data = skus_res.json()
    skus = skus_data.get('data', {}).get('items', []) if skus_data.get('status') == 'success' else []
    test_sku = skus[0] if skus else {'public_id': sku.public_id, 'code': sku.code, 'name': sku.name}
    
    boms_res = client.get(f"/api/v1/master/boms/{test_sku['public_id']}", headers=headers)
    boms_data = boms_res.json()
    bom_items = boms_data.get('data', {}).get('items', []) if boms_data.get('status') == 'success' else []
    
    test_mat_code = bom_items[0]['material']['code'] if bom_items else 'FR000649E'
    test_mat_name = bom_items[0]['material']['name'] if bom_items else 'Test Material'
    
    print_section("Pre-requisites loaded")
    print(f"Using SKU: {test_sku['code']} - {test_sku['name']}")
    print(f"Using RM/PM Material: {test_mat_code} - {test_mat_name}")

    # Generate ODS Excel in memory
    today = datetime.date.today().strftime('%Y-%m-%d')
    ods_df = pd.DataFrame([
        {
            'Business Date': today,
            'SKU': test_sku['code'],
            'FG Quantity': 100,
            'Material': test_mat_code,
            'Material Type (RM / PM)': 'RM',
            'Remaining Quantity': 0
        }
    ])
    ods_excel = BytesIO()
    ods_df.to_excel(ods_excel, index=False)
    ods_excel.seek(0)
    
    # Generate RMPM Excel in memory
    rmpm_df = pd.DataFrame([
        {
            'Business Date': today,
            'Material Code': test_mat_code,
            'Material Name': test_mat_name,
            'Current Stock': 50000 
        }
    ])
    rmpm_excel = BytesIO()
    rmpm_df.to_excel(rmpm_excel, index=False)
    rmpm_excel.seek(0)

    print_section("1. Upload ODS Excel and Show Preview (BOM Expansion)")
    upload_res = client.post(
        '/api/v1/requests/upload/preview', 
        files={'file': ('ods.xlsx', ods_excel, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, 
        headers=headers
    )
    preview_res_data = upload_res.json()
    preview_data = preview_res_data.get('data', {}) if preview_res_data.get('success') else preview_res_data
    print("ODS Preview Response:")
    print(json.dumps(preview_data, indent=2, cls=DecimalEncoder))
    if preview_data.get('errors'):
        print("Failed to preview ODS Excel.")
        return

    print_section("2. Commit the ODS Upload")
    commit_res = client.post('/api/v1/requests/upload/commit', json=preview_data, headers=headers)
    commit_res_data = commit_res.json()
    commit_data = commit_res_data.get('data', {}) if commit_res_data.get('success') else commit_res_data
    print("ODS Commit Response:")
    print(json.dumps(commit_data, indent=2, cls=DecimalEncoder))
    
    req_ids = commit_data.get('request_ids', [])
    if not req_ids:
        print("Failed to create request.")
        return
    request_public_id = req_ids[0]

    print_section("3. Show the generated Material Request")
    req_res = client.get(f'/api/v1/requests/{request_public_id}', headers=headers)
    req_res_data = req_res.json()
    req_details = req_res_data.get('data', {}) if req_res_data.get('success') else req_res_data
    print(json.dumps(req_details, indent=2, cls=DecimalEncoder))
    
    print_section("4. Upload the RMPM Inventory Excel")
    print(f"RMPM Inventory BEFORE Snapshot upload: {get_inventory('RMPM Warehouse', test_mat_code)} kg")
    rmpm_preview_res = client.post(
        '/api/v1/inventory/upload/preview', 
        files={'file': ('rmpm.xlsx', rmpm_excel, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, 
        headers=headers
    )
    rmpm_commit_res = client.post(
        '/api/v1/inventory/upload/commit', 
        files={'file': ('rmpm.xlsx', BytesIO(rmpm_excel.getvalue()), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, 
        headers=headers
    )
    print("RMPM Commit Response:")
    print(json.dumps(rmpm_commit_res.json(), indent=2, cls=DecimalEncoder))

    print_section("5. Show warehouse inventory BEFORE approval")
    rmpm_inv_before = get_inventory('RMPM', test_mat_code)
    ods_inv_before = get_inventory('ODS', test_mat_code)
    print(f"RMPM Warehouse: {rmpm_inv_before} kg")
    print(f"ODS Warehouse: {ods_inv_before} kg")

    print_section("6. Approve the generated request")
    rmpm_warehouse = db.query(Warehouse).filter_by(type='RMPM').first()
    rmpm_warehouse_public_id = str(rmpm_warehouse.public_id)
        
    all_items = [item for sku in req_details.get('skus', []) for item in sku.get('items', [])]
    
    approve_res = client.put(f'/api/v1/requests/{request_public_id}/approve', json={
        "rmpm_warehouse_public_id": rmpm_warehouse_public_id,
        "items": [
            {
                "material_public_id": str(item['material_public_id']),
                "approved_qty": item['requested_qty']
            } for item in all_items
        ]
    }, headers=headers)
    print(f"Approve Response: {approve_res.status_code} - {approve_res.json()}")
    
    # Must Dispatch first, then Receive
    dispatch_res = client.post(f'/api/v1/requests/{request_public_id}/dispatch', headers=headers)
    print(f"Dispatch Response: {dispatch_res.status_code} - {dispatch_res.json()}")

    print_section("7. Show warehouse inventory AFTER approval/dispatch")
    rmpm_inv_after = get_inventory('RMPM', test_mat_code)
    ods_inv_after = get_inventory('ODS', test_mat_code)
    print(f"RMPM Warehouse: {rmpm_inv_after} kg (Delta: {rmpm_inv_after - rmpm_inv_before})")
    print(f"ODS Warehouse: {ods_inv_after} kg (Delta: {ods_inv_after - ods_inv_before})")

    print_section("8. Confirm receipt in ODS")
    receive_res = client.post(f'/api/v1/requests/{request_public_id}/receive', headers=headers)
    print(f"Receive Response: {receive_res.status_code} - {receive_res.json()}")

    print_section("9. Show ODS inventory AFTER receipt")
    rmpm_inv_final = get_inventory('RMPM', test_mat_code)
    ods_inv_final = get_inventory('ODS', test_mat_code)
    print(f"RMPM Warehouse: {rmpm_inv_final} kg")
    print(f"ODS Warehouse: {ods_inv_final} kg (Delta: {ods_inv_final - ods_inv_after})")
    
    print_section("10. Show reports/dashboards reflecting transaction")
    dash_res = client.get('/api/v1/reports/inventory-trends', headers=headers)
    print("Inventory Trends Report (Snippet):")
    print(json.dumps(dash_res.json(), indent=2, cls=DecimalEncoder)[:500] + "...\n")
    
    trans_res = client.get('/api/v1/inventory/transactions', headers=headers)
    trans_data = trans_res.json()
    print("Recent Transactions:")
    items = trans_data.get('data', {}).get('items', []) if trans_data.get('status') == 'success' else []
    for t in items[:5]:
        print(f" - {t['transaction_date']} | {t['transaction_type']} | {t['material']['code']} | {t.get('source_warehouse', {}).get('name', 'N/A')} -> {t.get('destination_warehouse', {}).get('name', 'N/A')} | {t['quantity']}")


if __name__ == "__main__":
    run_workflow()
