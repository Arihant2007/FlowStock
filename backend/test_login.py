import sys
import logging

logging.basicConfig(level=logging.DEBUG)

try:
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    print("Sending login request...")
    response = client.post("/api/v1/auth/login", json={"identifier": "admin", "password": "............"})
    print("Status:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    import traceback
    traceback.print_exc()
