import requests
import os
import json

BASE_URL = "http://localhost:8000/api/v1"

CREDENTIALS = {
    "admin": {"identifier": "admin", "password": "Admin@12345"},
    "ods_op": {"identifier": "ods_op", "password": "OdsOp@12345"},
    "rmpm_op": {"identifier": "rmpm_op", "password": "Rmpm@12345"}
}

tokens = {}
results = {"auth": [], "rbac": [], "master_data": [], "uploads": []}

def test_login():
    print("Testing Authentication...")
    for role, creds in CREDENTIALS.items():
        res = requests.post(f"{BASE_URL}/auth/login", json=creds)
        if res.status_code == 200:
            tokens[role] = res.json().get("data", {}).get("access_token")
            results["auth"].append({
                "role": role, 
                "status": "Pass", 
                "expected": 200, 
                "actual": res.status_code, 
                "response": "Token Received"
            })
        else:
            results["auth"].append({
                "role": role, 
                "status": "Fail", 
                "expected": 200, 
                "actual": res.status_code, 
                "response": res.text
            })
            
    # Test invalid login
    res = requests.post(f"{BASE_URL}/auth/login", json={"identifier": "admin", "password": "wrongpassword"})
    results["auth"].append({
        "scenario": "Invalid Password",
        "status": "Pass" if res.status_code == 401 else "Fail",
        "expected": 401,
        "actual": res.status_code
    })

def test_rbac():
    print("Testing RBAC...")
    # Admin accesses everything
    # ODS operator should not be able to access RMPM uploads
    headers = {"Authorization": f"Bearer {tokens['ods_op']}"}
    res = requests.post(f"{BASE_URL}/inventory/upload/preview", headers=headers)
    results["rbac"].append({
        "scenario": "ODS Operator accessing RMPM Upload",
        "expected_status": [403, 401],
        "actual": res.status_code,
        "status": "Pass" if res.status_code in [403, 401] else "Fail",
        "response": res.text[:200]
    })
    
    # RMPM operator should not be able to access ODS uploads
    headers = {"Authorization": f"Bearer {tokens['rmpm_op']}"}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers)
    results["rbac"].append({
        "scenario": "RMPM Operator accessing ODS Upload",
        "expected_status": [403, 401],
        "actual": res.status_code,
        "status": "Pass" if res.status_code in [403, 401] else "Fail",
        "response": res.text[:200]
    })

def test_master_data():
    print("Testing Master Data...")
    headers = {"Authorization": f"Bearer {tokens['admin']}"}
    
    # Warehouses
    res = requests.get(f"{BASE_URL}/master/warehouses", headers=headers)
    results["master_data"].append({
        "endpoint": "/master/warehouses",
        "status": "Pass" if res.status_code == 200 else "Fail",
        "count": len(res.json().get("data", [])) if res.status_code == 200 else 0
    })
    
    # Materials
    res = requests.get(f"{BASE_URL}/master/materials", headers=headers)
    data = res.json().get("data", [])
    if isinstance(data, dict):
        data = data.get("items", [])
    results["master_data"].append({
        "endpoint": "/master/materials",
        "status": "Pass" if res.status_code == 200 else "Fail",
        "count": len(data) if res.status_code == 200 else 0
    })
    
    # SKUs
    res = requests.get(f"{BASE_URL}/master/skus", headers=headers)
    data = res.json().get("data", [])
    if isinstance(data, dict):
        data = data.get("items", [])
    results["master_data"].append({
        "endpoint": "/master/skus",
        "status": "Pass" if res.status_code == 200 else "Fail",
        "count": len(data) if res.status_code == 200 else 0
    })

import pandas as pd
from io import BytesIO

def test_excel_uploads():
    print("Testing Excel Uploads...")
    headers = {"Authorization": f"Bearer {tokens['ods_op']}"}
    
    # 1. Valid ODS Upload
    df_valid = pd.DataFrame([
        {
            "Business Date": "2026-07-22",
            "SKU": "FG-CHIPS-100", 
            "FG Quantity": 5000,
            "Material": "RM-POT-01",
            "Remaining Quantity": 500
        },
        {
            "Business Date": "2026-07-22",
            "SKU": "FG-CHIPS-100", 
            "FG Quantity": 5000,
            "Material": "RM-OIL-01",
            "Remaining Quantity": 50
        }
    ])
    excel_file = BytesIO()
    df_valid.to_excel(excel_file, index=False)
    excel_file.seek(0)
    
    files = {"file": ("ods_upload.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers, files=files)
    
    results["uploads"].append({
        "scenario": "Valid ODS Preview",
        "status": "Pass" if res.status_code == 200 else "Fail",
        "expected": 200,
        "actual": res.status_code,
        "response": res.text[:200] if res.status_code != 200 else "Preview Success"
    })
    
    # 2. Invalid Template (Missing Columns)
    df_invalid = pd.DataFrame([{"Wrong Column": 123}])
    excel_invalid = BytesIO()
    df_invalid.to_excel(excel_invalid, index=False)
    excel_invalid.seek(0)
    
    files_invalid = {"file": ("ods_invalid.xlsx", excel_invalid, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers, files=files_invalid)
    
    results["uploads"].append({
        "scenario": "Invalid ODS Columns",
        "status": "Pass" if res.status_code == 400 else "Fail",
        "expected": 400,
        "actual": res.status_code,
        "response": res.text[:200]
    })
    
    # 3. Invalid File Type
    files_txt = {"file": ("test.txt", b"hello world", "text/plain")}
    res = requests.post(f"{BASE_URL}/requests/upload/preview", headers=headers, files=files_txt)
    
    results["uploads"].append({
        "scenario": "Invalid File Type",
        "status": "Pass" if res.status_code == 400 else "Fail",
        "expected": 400,
        "actual": res.status_code,
        "response": res.text[:200]
    })

if __name__ == "__main__":
    try:
        test_login()
        if "ods_op" in tokens and "rmpm_op" in tokens:
            test_rbac()
        if "admin" in tokens:
            test_master_data()
        if "ods_op" in tokens:
            test_excel_uploads()
    except Exception as e:
        print("Error:", e)
        
    print(json.dumps(results, indent=2))
