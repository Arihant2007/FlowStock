import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import all models to ensure Base.metadata has them registered
from app.domains.audit.models import AuditLog  # noqa: F401
from app.domains.auth.models import Permission, Role, RolePermission, User  # noqa: F401
from app.domains.inventory.models import (  # noqa: F401
    InventorySnapshot,
    InventoryTransaction,
)
from app.domains.master.models import (  # noqa: F401
    SKU,
    BOMItem,
    BOMVersion,
    Material,
    MaterialCategory,
    MaterialType,
    Warehouse,
)
from app.domains.requests.models import (  # noqa: F401
    MaterialRequest,
    MaterialRequestItem,
    MaterialRequestSKU,
)
from app.domains.settings.models import Setting  # noqa: F401
from app.infrastructure.base_model import Base
from app.infrastructure.database import get_db
from app.main import app

# Create a fresh test database for the E2E verification
SQLALCHEMY_DATABASE_URL = "sqlite:///./e2e_test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def run_e2e():
    print("--- Starting End-to-End Business Workflow Verification ---")

    # 1. Login as Admin
    # Wait, we need to create the admin user first. Our app uses seeded users or we can seed them via a script.
    # Let's just import the seed function and seed the database.
    from seed import seed

    with TestingSessionLocal() as db:
        seed(db)

    print("\n[SUCCESS] Seeded initial data (Admin, Operators, Master Data).")

    # Login as Admin
    resp = client.post(
        "/api/v1/auth/login", json={"identifier": "admin", "password": "Admin@12345"}
    )
    assert resp.status_code == 200, resp.text
    admin_token = resp.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[SUCCESS] Logged in as Admin.")

    # 2. Create Warehouse
    resp = client.post(
        "/api/v1/master/warehouses",
        json={"name": "E2E RMPM Warehouse", "type": "RMPM"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    rmpm_wh_id = resp.json()["data"]["public_id"]

    resp = client.post(
        "/api/v1/master/warehouses",
        json={"name": "E2E ODS Warehouse", "type": "ODS"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    ods_wh_id = resp.json()["data"]["public_id"]
    print("[SUCCESS] Created RMPM and ODS Warehouses.")

    # 3. Retrieve Seeded Master Data
    mat_resp = client.get("/api/v1/master/materials", headers=admin_headers)
    mats_data = mat_resp.json().get("data", [])
    mats = mats_data.get("items", []) if isinstance(mats_data, dict) else mats_data
    rm1_id = next(m["public_id"] for m in mats if m["code"] == "RM-001")

    with TestingSessionLocal() as db:
        rm1_int_id = db.query(Material).filter_by(code="RM-001").first().id
        rm2_int_id = db.query(Material).filter_by(code="RM-002").first().id
    print("[SUCCESS] Retrieved Seeded Raw Materials.")

    sku_resp = client.get("/api/v1/master/skus", headers=admin_headers)
    skus_data = sku_resp.json().get("data", [])
    skus = skus_data.get("items", []) if isinstance(skus_data, dict) else skus_data
    sku_id = next(s["public_id"] for s in skus if s["code"] == "SKU-BISCUIT-500")
    print("[SUCCESS] Retrieved Seeded SKU and BOM.")

    # 6. Upload RMPM Inventory
    df_rmpm = pd.DataFrame(
        {
            "Material Code": ["RM-001", "RM-002"],
            "Quantity": [1000, 500],
            "UoM": ["KG", "L"],
            "Warehouse": ["E2E RMPM Warehouse", "E2E RMPM Warehouse"],
            "Date": ["01/01/2026", "01/01/2026"],
        }
    )
    buf_rmpm = io.BytesIO()
    with pd.ExcelWriter(buf_rmpm, engine="openpyxl") as writer:
        df_rmpm.to_excel(writer, index=False)
    buf_rmpm.seek(0)
    resp = client.post(
        "/api/v1/inventory/upload/commit",
        files={
            "file": (
                "rmpm.xlsx",
                buf_rmpm,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] Uploaded RMPM Inventory Snapshot.")

    # 7. Upload ODS Inventory (Remaining quantities)
    df_ods = pd.DataFrame(
        {
            "Material Code": ["RM-001"],
            "Quantity": [10],  # 10 KG remaining at ODS
            "UoM": ["KG"],
            "Warehouse": ["E2E ODS Warehouse"],
            "Date": ["01/01/2026"],
        }
    )
    buf_ods = io.BytesIO()
    with pd.ExcelWriter(buf_ods, engine="openpyxl") as writer:
        df_ods.to_excel(writer, index=False)
    buf_ods.seek(0)
    resp = client.post(
        "/api/v1/inventory/upload/commit",
        files={
            "file": (
                "ods.xlsx",
                buf_ods,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] Uploaded ODS Inventory Snapshot.")

    # Login as ODS Operator
    resp = client.post(
        "/api/v1/auth/login", json={"identifier": "ods_op", "password": "OdsOp@12345"}
    )
    ods_token = resp.json()["data"]["access_token"]
    ods_headers = {"Authorization": f"Bearer {ods_token}"}

    # 8. Create ODS Material Request
    # ODS requests to manufacture 100 SKUs.
    payload = {
        "request_date": "2026-01-02",
        "skus": [
            {
                "sku_public_id": sku_id,
                "planned_production_qty": 100,
                "remaining_rm": [{"material_public_id": rm1_id, "remaining_qty": 10}],
                "remaining_pm": [],
            }
        ],
    }
    resp = client.post("/api/v1/requests", json=payload, headers=ods_headers)
    assert resp.status_code == 201, resp.text
    req_data = resp.json().get("data", {})
    req_id = req_data.get("public_id")
    print("[SUCCESS] Created ODS Material Request.")

    # 9. Backend calculates RM/PM requirements
    # Let's check the created request items
    resp = client.get(f"/api/v1/requests/{req_id}", headers=ods_headers)
    req_data = resp.json()["data"]
    items = req_data["skus"][0]["items"]
    # SKU needs RM1: 2.5 * 100 = 250. Remaining = 10. Net = 240.
    # SKU needs RM2: 1.0 * 100 = 100. Remaining = 0. Net = 100.
    rm1_item = next(i for i in items if i["material_id"] == rm1_int_id)
    rm2_item = next(i for i in items if i["material_id"] == rm2_int_id)
    # Biscuit 500g has: RM-001 (0.2500), RM-002 (0.0500), PM-001 (1.0000)
    # 100 SKUs = 25 RM-001, 5 RM-002, 100 PM-001
    # Remaining = 10 RM-001
    # Net = 15 RM-001, 5 RM-002
    assert float(rm1_item["requested_qty"]) == 15.0
    assert float(rm2_item["requested_qty"]) == 5.0
    print(
        "[SUCCESS] Backend correctly calculated Net RM/PM Requirements (15 RM1, 5 RM2)."
    )

    # Login as RMPM Operator
    resp = client.post(
        "/api/v1/auth/login", json={"identifier": "rmpm_op", "password": "Rmpm@12345"}
    )
    rmpm_token = resp.json()["data"]["access_token"]
    rmpm_headers = {"Authorization": f"Bearer {rmpm_token}"}

    # 10. RMPM reserves inventory
    resp = client.post(f"/api/v1/requests/{req_id}/reserve", headers=rmpm_headers)
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] RMPM Operator reserved inventory.")

    # 11. Approves request
    item1_id = rm1_item["public_id"]
    item2_id = rm2_item["public_id"]

    approve_payload = {
        "rmpm_warehouse_public_id": rmpm_wh_id,
        "ods_warehouse_public_id": ods_wh_id,
        "items": [
            {"material_request_item_public_id": item1_id, "approved_qty": 15},
            {"material_request_item_public_id": item2_id, "approved_qty": 5},
        ],
    }
    resp = client.put(
        f"/api/v1/requests/{req_id}/approve", json=approve_payload, headers=rmpm_headers
    )
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] RMPM Operator approved request.")

    # 12. Dispatches materials
    resp = client.post(f"/api/v1/requests/{req_id}/dispatch", headers=rmpm_headers)
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] RMPM Operator dispatched materials.")

    # 13. ODS receives materials
    resp = client.post(f"/api/v1/requests/{req_id}/receive", headers=ods_headers)
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] ODS Operator received materials.")

    # 14. Close request
    resp = client.post(f"/api/v1/requests/{req_id}/close", headers=ods_headers)
    assert resp.status_code == 200, resp.text
    print("[SUCCESS] Request Closed.")

    # 15. Verify Inventory Ledger
    resp = client.get("/api/v1/inventory/balances", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    balances_data = resp.json().get("data", [])
    balances = (
        balances_data.get("items", [])
        if isinstance(balances_data, dict)
        else balances_data
    )

    rmpm_rm1 = next(
        (
            b
            for b in balances
            if b["warehouse_name"] == "E2E RMPM Warehouse"
            and b["material_code"] == "RM-001"
        ),
        None,
    )
    ods_rm1 = next(
        (
            b
            for b in balances
            if b["warehouse_name"] == "E2E ODS Warehouse"
            and b["material_code"] == "RM-001"
        ),
        None,
    )

    assert rmpm_rm1 and float(rmpm_rm1["available_balance"]) == 985.0
    assert ods_rm1 and float(ods_rm1["available_balance"]) == 25.0
    print("[SUCCESS] Inventory Ledger verified (Balances updated correctly).")

    # Check Reports (Transactions)
    resp = client.get(
        f"/api/v1/inventory/transactions?material_public_id={rm1_id}",
        headers=admin_headers,
    )
    txs = resp.json()["data"]
    assert any(tx["transaction_type"] == "TRANSFER_OUT" for tx in txs)
    assert any(tx["transaction_type"] == "TRANSFER_IN" for tx in txs)
    print("[SUCCESS] Transaction History verified.")

    print("\n==============================================")
    print("SUCCESS: End-to-End Business Workflow Verified!")
    print("==============================================")


if __name__ == "__main__":
    run_e2e()
