import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database import SessionLocal, engine
from app.domains.master.models import MaterialCategory, MaterialType, Material, Warehouse
from app.domains.inventory.models import InventoryTransaction, InventorySnapshot
import uuid
import datetime
import json
from decimal import Decimal

# Custom JSON encoder to handle Decimal objects gracefully
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

db = SessionLocal()

# Provide minimum setup
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

materials = [
    'FR000649E', 'FR001373', 'FR000629', 'FR004305', 'FLS704IS',
    'FPSX02899', 'FPSX03148', 'FPSX00698', 'FFSNFMOHCHIPS', 
    'FFSNOFMOHCHIPS', 'FFSNVMOHCHIPS', 'FPSX03390', 'FPSX03593', 'FPSX02900', 'FPSX02781', 'FPSX03396',
    'FPSX03129', 'FPSX02783', 'FPSX03392'
]
for code in materials:
    if not db.query(Material).filter_by(code=code).first():
        db.add(Material(code=code, name=code, category_id=cat.id, type_id=typ.id, uom='KG', created_by=1))
db.commit()

mat_potato = db.query(Material).filter_by(code='FR000649E').first()
if mat_potato:
    existing_snap = db.query(InventorySnapshot).filter_by(material_id=mat_potato.id, warehouse_id=wh_ods.id, snapshot_date=datetime.date.today() - datetime.timedelta(days=1)).first()
    if not existing_snap:
        db.add(InventorySnapshot(material_id=mat_potato.id, warehouse_id=wh_ods.id, snapshot_date=datetime.date.today() - datetime.timedelta(days=1), closing_balance=Decimal("20000.00"), created_by=1))
        db.add(InventoryTransaction(material_id=mat_potato.id, destination_warehouse_id=wh_ods.id, transaction_type='RECEIPT', quantity=Decimal("20000.00"), reference_type='TEST', reference_id=1, created_by=1))
        db.commit()

client = TestClient(app)

from app.domains.auth.dependencies import get_current_user

class MockUser:
    id = 1
    public_id = uuid.uuid4()
    username = "admin"
    email = "admin@itc.in"
    full_name = "Admin"
    role_id = 1
    is_active = True
    created_at = datetime.datetime.now()
    updated_at = None

def override_get_current_user():
    return MockUser()

app.dependency_overrides[get_current_user] = override_get_current_user
headers = {}

print('\n--- 1. BOM UPLOAD PREVIEW ---')
with open('Skus_Bom.xlsx', 'rb') as f:
    upload_res = client.post('/api/v1/master/boms/upload/preview', files={'file': ('Skus_Bom.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, headers=headers)
print(json.dumps(upload_res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 2. BOM UPLOAD COMMIT ---')
with open('Skus_Bom.xlsx', 'rb') as f:
    commit_res = client.post('/api/v1/master/boms/upload/commit', files={'file': ('Skus_Bom.xlsx', f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}, headers=headers)
print(json.dumps(commit_res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 3. SKUS IN DB ---')
skus_res = client.get('/api/v1/master/skus', headers=headers)
sku_code = 'FXC70010SL'
sku_public_id = None
for s in skus_res.json()['items']:
    if s['code'] == sku_code:
        sku_public_id = s['public_id']
    print(f"{s['code']} - {s['name']}")

if sku_public_id:
    print(f'\n--- 4. BOM FOR {sku_code} ---')
    boms_res = client.get(f'/api/v1/master/boms/{sku_public_id}', headers=headers)
    print(json.dumps(boms_res.json(), indent=2, cls=DecimalEncoder))

    print('\n--- 5. ODS REQUEST CREATION ---')
    req_payload = {
        'request_date': datetime.date.today().isoformat(),
        'notes': 'Test request for 5 units',
        'ods_warehouse_public_id': str(wh_ods.public_id),
        'skus': [
            {'sku_public_id': str(sku_public_id), 'planned_production_qty': 5.0}
        ]
    }
    req_res = client.post('/api/v1/requests', json=req_payload, headers=headers)
    print(json.dumps(req_res.json(), indent=2, cls=DecimalEncoder))
else:
    print(f'\nSKU {sku_code} not found in DB')
