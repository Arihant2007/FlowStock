"""Comprehensive test suite for the auth domain service layer.

Tests run against an in-memory SQLite database (no Postgres required).
Every test is wrapped in a rolled-back transaction for isolation.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import (
    AccountLockedError,
    AuthenticationError,
    DuplicateError,
    TokenRevokedError,
)
from app.domains.auth.models import (
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    User,
)
from app.domains.auth.security import hash_password
from app.domains.auth.service import MAX_FAILED_ATTEMPTS, AuthService
from app.infrastructure.base_model import Base

# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(bind=_engine)
_SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a session wrapped in a savepoint, rolled back after each test."""
    session = _SessionFactory()
    session.begin_nested()  # SAVEPOINT — rolls back to here on fixture teardown
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_role_with_perm(
    db: Session, role_name: str = "ADMIN"
) -> tuple[Role, Permission]:
    perm = Permission(code="auth:login", description="Login", created_by=None)
    role = Role(name=role_name, created_by=None)
    db.add_all([perm, role])
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=perm.id, created_by=None))
    db.flush()
    return role, perm


def _seed_user(db: Session, role: Role, *, username: str = "testuser") -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Test User",
        password_hash=hash_password("Password@123"),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success_with_username(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        _seed_user(db, role)
        tokens = AuthService(db).login("testuser", "Password@123")
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "bearer"
        assert "auth:login" in tokens.permissions

    def test_login_success_with_email(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        _seed_user(db, role)
        tokens = AuthService(db).login("testuser@test.com", "Password@123")
        assert tokens.access_token

    def test_login_wrong_password(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        _seed_user(db, role)
        with pytest.raises(AuthenticationError):
            AuthService(db).login("testuser", "WrongPassword!")

    def test_login_unknown_identifier(self, db: Session) -> None:
        with pytest.raises(AuthenticationError):
            AuthService(db).login("nobody@nowhere.com", "Password@123")

    def test_login_inactive_user(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        user.is_active = False
        db.flush()
        with pytest.raises(AuthenticationError, match="deactivated"):
            AuthService(db).login("testuser", "Password@123")

    def test_login_resets_failed_count_on_success(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        user.failed_login_count = 3
        db.flush()
        AuthService(db).login("testuser", "Password@123")
        assert user.failed_login_count == 0

    def test_login_creates_refresh_session(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        AuthService(db).login("testuser", "Password@123")
        sessions = db.query(RefreshSession).filter_by(user_id=user.id).all()
        assert len(sessions) == 1
        assert sessions[0].revoked is False


# ---------------------------------------------------------------------------
# Account lockout tests
# ---------------------------------------------------------------------------


class TestAccountLockout:
    def test_account_locked_after_max_failures(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role, username="lockout_user")
        svc = AuthService(db)

        for _ in range(MAX_FAILED_ATTEMPTS):
            with pytest.raises(AuthenticationError):
                svc.login("lockout_user", "WrongPass!")

        assert user.locked_until is not None
        with pytest.raises(AccountLockedError):
            svc.login("lockout_user", "Password@123")  # Even correct password blocked.

    def test_locked_account_unblocks_after_time(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role, username="expired_lock_user")
        # Manually set lock to the past.
        user.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        user.failed_login_count = MAX_FAILED_ATTEMPTS
        db.flush()
        # Login should succeed after lock expires.
        tokens = AuthService(db).login("expired_lock_user", "Password@123")
        assert tokens.access_token


# ---------------------------------------------------------------------------
# Token refresh tests
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    def test_refresh_roundtrip(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        _seed_user(db, role)
        svc = AuthService(db)
        tokens = svc.login("testuser", "Password@123")
        new_tokens = svc.refresh(tokens.refresh_token)
        assert new_tokens.access_token
        assert new_tokens.access_token != tokens.access_token

    def test_refresh_rotates_session(self, db: Session) -> None:
        """Old jti should be revoked; new jti should be active."""
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        svc = AuthService(db)
        tokens = svc.login("testuser", "Password@123")
        svc.refresh(tokens.refresh_token)
        sessions = db.query(RefreshSession).filter_by(user_id=user.id).all()
        revoked = [s for s in sessions if s.revoked]
        active = [s for s in sessions if not s.revoked]
        assert len(revoked) == 1
        assert len(active) == 1

    def test_refresh_with_access_token_raises(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        _seed_user(db, role)
        svc = AuthService(db)
        tokens = svc.login("testuser", "Password@123")
        with pytest.raises(AuthenticationError, match="not a refresh token"):
            svc.refresh(tokens.access_token)

    def test_refresh_revoked_token_raises(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        svc = AuthService(db)
        tokens = svc.login("testuser", "Password@123")
        # Revoke the session directly.
        db.query(RefreshSession).filter_by(user_id=user.id).update({"revoked": True})
        db.flush()
        with pytest.raises(TokenRevokedError):
            svc.refresh(tokens.refresh_token)


# ---------------------------------------------------------------------------
# Logout tests
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_revokes_session(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        svc = AuthService(db)
        tokens = svc.login("testuser", "Password@123")
        svc.logout(tokens.refresh_token, user_id=user.id)
        session = db.query(RefreshSession).filter_by(user_id=user.id).first()
        assert session is not None
        assert session.revoked is True

    def test_logout_invalid_token_is_silent(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        # Should not raise even with a completely invalid token.
        AuthService(db).logout("not.a.real.token", user_id=user.id)

    def test_logout_all_revokes_all_sessions(self, db: Session) -> None:
        role, _ = _seed_role_with_perm(db)
        user = _seed_user(db, role)
        svc = AuthService(db)
        svc.login("testuser", "Password@123")
        svc.login("testuser", "Password@123")
        count = svc.logout_all(user_id=user.id)
        assert count == 2
        sessions = db.query(RefreshSession).filter_by(user_id=user.id).all()
        assert all(s.revoked for s in sessions)


# ---------------------------------------------------------------------------
# User management tests
# ---------------------------------------------------------------------------


class TestUserManagement:
    def test_create_user_success(self, db: Session) -> None:
        from app.domains.auth.schemas import CreateUserRequest

        role, _ = _seed_role_with_perm(db)
        admin = _seed_user(db, role, username="admin")
        payload = CreateUserRequest(
            username="newuser",
            email="new@example.com",
            full_name="New Operator",
            password="StrongPass@123",
            role_public_id=role.public_id,
        )
        user = AuthService(db).create_user(payload, created_by=admin.id)
        assert user.username == "newuser"

    def test_create_user_duplicate_username(self, db: Session) -> None:
        from app.domains.auth.schemas import CreateUserRequest

        role, _ = _seed_role_with_perm(db)
        admin = _seed_user(db, role, username="admin2")
        _seed_user(db, role, username="existing")
        payload = CreateUserRequest(
            username="existing",
            email="unique@example.com",
            full_name="Another",
            password="StrongPass@123",
            role_public_id=role.public_id,
        )
        with pytest.raises(DuplicateError):
            AuthService(db).create_user(payload, created_by=admin.id)
