import requests

BASE_URL = "http://localhost:8000/api/v1"
res = requests.post(f"{BASE_URL}/auth/login", json={"identifier": "admin", "password": "Admin@12345"})
if res.status_code != 200:
    print("Login failed:", res.text)
    exit(1)
    
token = res.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test Trends
print("Testing Trends...")
r = requests.get(f"{BASE_URL}/reports/inventory-trends?days=7", headers=headers)
print("Trends Response:", r.status_code)
if r.status_code == 200:
    print(r.json()["data"])
else:
    print(r.text)

# Test PDF
print("\nTesting PDF...")
r = requests.get(f"{BASE_URL}/reports/variance/export?format=pdf", headers=headers)
print("PDF Response:", r.status_code)
print("Content-Type:", r.headers.get("Content-Type"))
if r.status_code == 200:
    with open("test_export.pdf", "wb") as f:
        f.write(r.content)
    import os
    print("PDF Size:", os.path.getsize("test_export.pdf"))
else:
    print(r.text)
