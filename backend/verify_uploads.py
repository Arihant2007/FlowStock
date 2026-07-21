import pandas as pd
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.domains.auth.dependencies import get_current_user
import uuid
import datetime
import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

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
        MockRolePermission("requests:write"),
        MockRolePermission("requests:read"),
    ]

class MockUser:
    id = 1
    public_id = uuid.uuid4()
    username = "admin"
    email = "admin@itc.in"
    full_name = "Admin"
    role_id = 1
    role = MockRole()
    is_active = True
    warehouse_id = None
    created_at = datetime.datetime.now()
    updated_at = None

def override_get_current_user():
    return MockUser()

app.dependency_overrides[get_current_user] = override_get_current_user

# 1. Create templates
df_materials = pd.DataFrame({
    'Material Code': ['FR000649E', 'FLS704IS'],
    'Material Name': ['Potato', 'Laminate'],
    'UOM': ['KG', 'KG'],
    'Category': ['Raw Material', 'Packaging Material'],
    'Material Type': ['RM', 'PM'],
    'Group': ['Ingredients', 'Laminates']
})
df_materials.to_excel("Material_Master_Template.xlsx", index=False)

df_inv = pd.DataFrame({
    'Material Code': ['FR000649E'],
    'Quantity': ['1500'],
    'UoM': ['KG'],
    'Warehouse': ['RMPM-Main'],
    'Date': [date.today().strftime("%d/%m/%Y")]
})
df_inv.to_excel("Inventory_Upload_Template.xlsx", index=False)

client = TestClient(app)
headers = {}

print('\n--- 1. MATERIAL MASTER PREVIEW ---')
with open('Material_Master_Template.xlsx', 'rb') as f:
    res = client.post('/api/v1/master/materials/upload/preview', files={'file': ('Material_Master_Template.xlsx', f)}, headers=headers)
print(json.dumps(res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 2. MATERIAL MASTER COMMIT ---')
with open('Material_Master_Template.xlsx', 'rb') as f:
    res = client.post('/api/v1/master/materials/upload/commit', files={'file': ('Material_Master_Template.xlsx', f)}, headers=headers)
print(json.dumps(res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 3. VERIFY MATERIALS IN DB ---')
res = client.get('/api/v1/master/materials', headers=headers)
materials = res.json().get('items', [])
for m in materials:
    if m['code'] in ['FR000649E', 'FLS704IS']:
        print(f"Found {m['code']} - {m['name']}")

print('\n--- 4. INVENTORY UPLOAD PREVIEW ---')
with open('Inventory_Upload_Template.xlsx', 'rb') as f:
    res = client.post('/api/v1/inventory/upload/preview', files={'file': ('Inventory_Upload_Template.xlsx', f)}, headers=headers)
print(json.dumps(res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 5. INVENTORY UPLOAD COMMIT ---')
with open('Inventory_Upload_Template.xlsx', 'rb') as f:
    res = client.post('/api/v1/inventory/upload/commit', files={'file': ('Inventory_Upload_Template.xlsx', f)}, headers=headers)
print(json.dumps(res.json(), indent=2, cls=DecimalEncoder))

print('\n--- 6. VERIFY DASHBOARD ---')
res = client.get('/api/v1/dashboard/metrics', headers=headers)
print(json.dumps(res.json(), indent=2, cls=DecimalEncoder))

