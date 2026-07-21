import sys
import os
import traceback
import pandas as pd
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.main import app
from fastapi.testclient import TestClient
from app.infrastructure.database import SessionLocal
from app.domains.auth.models import User
from app.domains.auth.security import create_access_token
from app.domains.master.service import MasterService

def test_cases():
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
        service = MasterService(db)

    headers = {"Authorization": f"Bearer {access_token}"}

    def run_file(name, data_dict):
        df = pd.DataFrame(data_dict)
        io = BytesIO()
        df.to_excel(io, index=False)
        content = io.getvalue()

        print(f"\n--- Testing {name} ---")
        files = {"file": (f"{name}.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp_p = client.post("/api/v1/master/materials/upload/preview", headers=headers, files=files)
        print("Preview status:", resp_p.status_code)
        p_json = resp_p.json()
        print("Preview error_rows:", p_json.get("data", {}).get("error_rows"))
        
        files = {"file": (f"{name}.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp_c = client.post("/api/v1/master/materials/upload/commit", headers=headers, files=files)
        print("Commit status:", resp_c.status_code)
        print("Commit response:", resp_c.text)
        if resp_c.status_code != 200:
            print("FAILED COMMIT!")

    # Case 1: Numeric material codes / UOM / Group
    run_file("numeric_codes", {
        "Material Code": [10001, 10002],
        "Material Name": ["Mat 10001", "Mat 10002"],
        "UOM": ["EA", "KG"],
        "Category": ["Packaging Material", "Raw Material"],
        "Material Type": ["PM", "RM"],
        "Group": ["Cartons", "Ingredients"]
    })

    # Case 2: Lowercase / uppercase variations
    run_file("case_variations", {
        "Material Code": ["MAT-LOWER-1"],
        "Material Name": ["Lower case test"],
        "UOM": ["ea"],
        "Category": ["packaging material"],
        "Material Type": ["pm"],
        "Group": ["cartons"]
    })

    # Case 3: Group column missing
    run_file("no_group_col", {
        "Material Code": ["MAT-NOGRP"],
        "Material Name": ["No Group Col"],
        "UOM": ["EA"],
        "Category": ["Packaging Material"],
        "Material Type": ["PM"]
    })

    # Case 4: Long material names / UOM
    run_file("trailing_spaces", {
        "Material Code": ["  MAT-SPACE-1  "],
        "Material Name": ["  Material with spaces  "],
        "UOM": ["  EA  "],
        "Category": ["  Packaging Material  "],
        "Material Type": ["  PM  "],
        "Group": ["  Cartons  "]
    })

if __name__ == "__main__":
    try:
        test_cases()
    except Exception as e:
        traceback.print_exc()
