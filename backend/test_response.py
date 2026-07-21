import sys
import asyncio
from http import HTTPStatus
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def test_route():
    return JSONResponse(content={"msg": "test"}, status_code=HTTPStatus.UNAUTHORIZED)

client = TestClient(app)

try:
    response = client.get("/")
    print("Status:", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()
