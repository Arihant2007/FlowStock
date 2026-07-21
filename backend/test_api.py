import sys
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from fastapi.testclient import TestClient
from app.infrastructure.database import SessionLocal
from app.domains.auth.models import User
from app.domains.auth.security import create_access_token

def test_api():
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
    
    import pandas as pd
    from io import BytesIO
    df = pd.DataFrame({
        "Material Code": ["FPSX03391-TEST-API"],
        "Material Name": ["Test API Material Updated"],
        "UOM": ["EA"],
        "Category": ["Packaging Material"],
        "Material Type": ["PM"],
        "Group": ["Cartons"]
    })
    excel_io = BytesIO()
    df.to_excel(excel_io, index=False)
    
    files = {"file": ("test_api.xlsx", excel_io.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post("/api/v1/master/materials/upload/commit", headers=headers, files=files)
    print("Status:", resp.status_code)
    print("Response:", resp.text)

if __name__ == "__main__":
    try:
        test_api()
    except Exception as e:
        traceback.print_exc()
