import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from fastapi.testclient import TestClient
from app.infrastructure.database import SessionLocal
from app.domains.auth.models import User
from app.domains.auth.security import create_access_token

def test_actual_template():
    client = TestClient(app)
    
    with SessionLocal() as db:
        user = db.query(User).filter_by(username="admin").first()
        permissions = [p.permission.code for p in user.role.permissions] if user.role else []
        access_token = create_access_token(
            subject=str(user.id),
            public_id=str(user.public_id),
            role=user.role.name if user.role else "",
            permissions=permissions
        )
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    file_path = os.path.join(os.path.dirname(__file__), "Material_Master_Template.xlsx")
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    print("Testing Preview...")
    files = {"file": ("Material_Master_Template.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp_prev = client.post("/api/v1/master/materials/upload/preview", headers=headers, files=files)
    print("Preview Status:", resp_prev.status_code)
    print("Preview Response:", resp_prev.text)
    
    print("\nTesting Commit...")
    files = {"file": ("Material_Master_Template.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp_commit = client.post("/api/v1/master/materials/upload/commit", headers=headers, files=files)
    print("Commit Status:", resp_commit.status_code)
    print("Commit Response:", resp_commit.text)

if __name__ == "__main__":
    try:
        test_actual_template()
    except Exception as e:
        traceback.print_exc()
