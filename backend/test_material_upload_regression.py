import os
import sys
import traceback
import uuid
from datetime import datetime, timezone
import pandas as pd
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from fastapi.testclient import TestClient
from app.infrastructure.database import SessionLocal
from app.domains.auth.models import User, Role, Permission, RolePermission
from app.domains.auth.security import create_access_token
from app.domains.master.models import Material

client = TestClient(app)

def setup_users():
    with SessionLocal() as db:
        user_with_write = db.query(User).filter_by(username="admin").first()
        perms_write = [p.permission.code for p in user_with_write.role.permissions] if user_with_write.role else []
        token_write = create_access_token(
            subject=str(user_with_write.id),
            public_id=str(user_with_write.public_id),
            role=user_with_write.role.name if user_with_write.role else "",
            permissions=perms_write
        )
        
        # Make a user without master:write
        dummy_role = db.query(Role).filter_by(name="dummy_role").first()
        if not dummy_role:
            dummy_role = Role(name="dummy_role")
            db.add(dummy_role)
            db.commit()
            db.refresh(dummy_role)

        user_without = db.query(User).filter_by(username="ods_operator").first()
        if not user_without:
            user_without = User(
                username="ods_operator",
                email="ods@example.com",
                full_name="ODS",
                password_hash="dummy",
                is_active=True,
                role_id=dummy_role.id
            )
            db.add(user_without)
            db.commit()
            db.refresh(user_without)
            
        token_read_only = create_access_token(
            subject=str(user_without.id),
            public_id=str(user_without.public_id),
            role=dummy_role.name,
            permissions=[]
        )
        
        return token_write, token_read_only

def make_excel(data: dict) -> bytes:
    df = pd.DataFrame(data)
    io = BytesIO()
    df.to_excel(io, index=False)
    return io.getvalue()

def send_commit(token, data_dict=None, file_bytes=None, filename="test.xlsx"):
    headers = {"Authorization": f"Bearer {token}"}
    if file_bytes is None:
        file_bytes = make_excel(data_dict)
    files = {"file": (filename, file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/master/materials/upload/commit", headers=headers, files=files)
    return resp

def run_tests():
    token_write, token_read = setup_users()
    
    print("1. Testing Missing Permissions (403 Expected)")
    resp = send_commit(token_read, {"Material Code": ["T1"]})
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    print("OK")
    
    print("2. Testing Empty File (400 Expected)")
    resp = send_commit(token_write, file_bytes=b"")
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
    print("OK")

    print("3. Testing Missing Required Fields (400 Expected from ValidationError)")
    resp = send_commit(token_write, {
        "Material Code": ["FPSX03391-REQ"],
        "Material Name": ["Test Req"],
        "UOM": ["EA"],
        "Category": [""],
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    print("OK")

    print("4. Testing Duplicate Rows in Same Upload (400 Expected from ValidationError)")
    resp = send_commit(token_write, {
        "Material Code": ["DUP1", "DUP1"],
        "Material Name": ["D1", "D2"],
        "UOM": ["EA", "EA"],
        "Category": ["Packaging Material", "Packaging Material"],
        "Material Type": ["PM", "PM"],
        "Group": ["Cartons", "Cartons"]
    })
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    print("OK")

    print("5. Testing New Material Upload")
    code = f"NEW-{uuid.uuid4().hex[:6]}"
    resp = send_commit(token_write, {
        "Material Code": [code],
        "Material Name": ["New Mat"],
        "UOM": ["EA"],
        "Category": ["Packaging Material"],
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["data"]["created"] == 1
    print("OK")

    print("6. Testing Existing Material Update")
    resp = send_commit(token_write, {
        "Material Code": [code],
        "Material Name": ["New Mat UPDATED"],
        "UOM": ["EA"],
        "Category": ["Packaging Material"],
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["data"]["updated"] == 1
    print("OK")

    print("7. Testing Soft-Deleted Material Restoration")
    with SessionLocal() as db:
        mat = db.query(Material).filter_by(code=code).first()
        mat.deleted_at = datetime.now(timezone.utc)
        mat.deleted_by = 1
        db.commit()

    resp = send_commit(token_write, {
        "Material Code": [code],
        "Material Name": ["New Mat UPDATED"],
        "UOM": ["EA"],
        "Category": ["Packaging Material"],
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json()["data"]["updated"] == 1 
    print("OK")
    
    print("8. Testing Invalid Data Types")
    # For example, numbers instead of strings for category
    # The normalizer casts everything to string, so it should process or fail safely if category name doesnt match.
    resp = send_commit(token_write, {
        "Material Code": ["FPSX-NUM"],
        "Material Name": ["Num"],
        "UOM": ["EA"],
        "Category": [123], # Not a string category
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    # Since 123 is not a valid Category in the db, it throws 400
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "does not exist" in resp.text
    print("OK")

    print("All regression tests passed successfully!")

if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        traceback.print_exc()
