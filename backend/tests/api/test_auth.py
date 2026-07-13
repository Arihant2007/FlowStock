"""API integration tests for auth endpoints using FastAPI TestClient.

These tests exercise the full HTTP stack: routing, request validation,
service logic, and response envelope.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domains.auth.models import Permission, Role, RolePermission, User
from app.domains.auth.security import hash_password
from app.infrastructure.base_model import Base
from app.infrastructure.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Test DB setup — single in-memory SQLite instance shared via StaticPool.
# This ensures all connections (create_all, seed, routes) see the same tables.
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_engine)
_SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def override_get_db():
    db = _SessionFactory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app, raise_server_exceptions=True)


def _seed_db() -> dict:
    """Seed a minimal test dataset. Returns credentials for use in tests."""
    db = _SessionFactory()
    try:
        perm = Permission(code="auth:login", description="Login")
        role = Role(name="ADMIN")
        db.add_all([perm, role])
        db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=perm.id))
        db.flush()
        user = User(
            username="api_testuser",
            email="apitest@plant.local",
            full_name="API Test",
            password_hash=hash_password("APIPass@123"),
            role_id=role.id,
            is_active=True,
        )
        db.add(user)
        db.commit()
        return {"username": "api_testuser", "password": "APIPass@123"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def seed():
    return _seed_db()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoginAPI:
    def test_login_success_username(self) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "APIPass@123"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["access_token"]
        assert data["data"]["token_type"] == "bearer"

    def test_login_success_email(self) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "apitest@plant.local", "password": "APIPass@123"},
        )
        assert resp.status_code == 200, resp.text

    def test_login_wrong_password(self) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "WrongPass!99"},
        )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_login_unknown_user(self) -> None:
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "ghost@nobody.com", "password": "Password@123"},
        )
        assert resp.status_code == 401

    def test_login_short_password_validation(self) -> None:
        """Pydantic validation rejects passwords < 8 chars before hitting the service."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "short"},
        )
        assert resp.status_code == 422


class TestRefreshAPI:
    def test_refresh_success(self) -> None:
        login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "APIPass@123"},
        )
        assert login.status_code == 200, login.text
        refresh_token = login.json()["data"]["refresh_token"]

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["access_token"]

    def test_refresh_with_garbage_token(self) -> None:
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not.a.token.at.all"},
        )
        assert resp.status_code == 401


class TestMeAPI:
    def test_me_authenticated(self) -> None:
        login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "APIPass@123"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["username"] == "api_testuser"

    def test_me_unauthenticated(self) -> None:
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_expired_token(self) -> None:
        """Using a clearly malformed/expired token should return 401."""
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.e30.invalid"},
        )
        assert resp.status_code == 401


class TestLogoutAPI:
    def test_logout_success(self) -> None:
        login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "api_testuser", "password": "APIPass@123"},
        )
        assert login.status_code == 200, login.text
        data = login.json()["data"]
        access = data["access_token"]
        refresh = data["refresh_token"]

        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 200, resp.text

        # Subsequent refresh attempt must fail.
        retry = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert retry.status_code == 401
