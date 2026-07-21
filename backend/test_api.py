import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from io import BytesIO
import pandas as pd
import uuid
import os

os.environ["DATABASE_URL"] = "sqlite:///test_skus_api.db"

from app.main import app
from app.infrastructure.database import get_db, Base, engine
from app.domains.auth.models import User, Role
from app.domains.master.models import MaterialCategory, MaterialType, Material, Warehouse

client = TestClient(app)

def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    role = Role(name="Admin", public_id=uuid.uuid4())
    db.add(role)
    db.flush()
    user = User(username="admin", email="admin@test.com", password_hash="hash", role_id=role.id)
    db.add(user)
    db.flush()
    
    cat = MaterialCategory(name="Raw Material", public_id=uuid.uuid4(), created_by=user.id)
    typ = MaterialType(name="Ingredient", public_id=uuid.uuid4(), created_by=user.id)
    db.add_all([cat, typ])
    db.flush()
    
    mat1 = Material(code="FR000649E", name="POTATO-EXTERNAL", category_id=cat.id, type_id=typ.id, uom="KG", created_by=user.id)
    mat2 = Material(code="FR001373", name="IODISED SALT - SUPER FINE", category_id=cat.id, type_id=typ.id, uom="KG", created_by=user.id)
    db.add_all([mat1, mat2])
    db.commit()
    db.close()
    return user.id

def test_bom_upload_skus():
    setup_db()
    
    def override_require_permission(perm):
        def _dep():
            Session = sessionmaker(bind=engine)
            db = Session()
            user = db.query(User).first()
            db.close()
            return user
        return _dep

    from app.domains.auth.dependencies import require_permission
    app.dependency_overrides[require_permission] = override_require_permission

    s1 = [
        ["FCC 10 RS", "FXC70010SL", "", ""],
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FR000649E", "POTATO-EXTERNAL", "3000", "KG"],
        ["FR001373", "IODISED SALT - SUPER FINE", "100", "KG"],
    ]
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(s1).to_excel(writer, sheet_name="Sheet1", header=False, index=False)
    
    file_bytes = output.getvalue()
    
    res = client.post("/api/master/boms/upload/preview", files={"file": ("bom.xlsx", file_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    session_id = res.json()["data"]["session_id"]
    
    res = client.post("/api/master/boms/upload/commit", data={"session_id": session_id})
    print("Commit response:", res.json())
    
    res = client.get("/api/master/skus")
    print("SKUs API status:", res.status_code)
    if res.status_code == 200:
        print("SKUs API returned:", res.json())
    else:
        print("SKUs API error:", res.text)

if __name__ == "__main__":
    test_bom_upload_skus()
