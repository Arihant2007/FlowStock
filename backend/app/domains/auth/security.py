"""JWT token issuance/verification and password hashing.

Password hashing:
  Uses pwdlib with Argon2id — actively maintained, recommended by
  the FastAPI ecosystem, resistant to GPU/ASIC attacks.

JWT design:
  Access tokens  — short-lived (15 min), carry role + permissions.
  Refresh tokens — long-lived (7 days), carry a jti that must match
                   an active RefreshSession row in the database.

JWT claims:
  sub         — user internal integer ID (string-cast)
  public_id   — user UUID (safe for external exposure)
  role        — role name string
  permissions — list[str] of permission codes
  token_type  — "access" | "refresh"
  exp         — expiry timestamp
  iat         — issued-at timestamp
  jti         — unique token identifier (UUID4 string)
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.errors import AuthenticationError

settings = get_settings()

# Argon2id is the recommended password hashing algorithm per OWASP 2024.
password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Return an Argon2id hash of the supplied plain-text password."""
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed: str) -> bool:
    """Return True if the plain password matches the Argon2id hash."""
    try:
        return password_hash.verify(plain_password, hashed)
    except Exception:  # noqa: BLE001
        return False


def _base_claims(
    subject: str,
    public_id: str,
    token_type: str,
    expire: datetime,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "public_id": public_id,
        "token_type": token_type,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
    }
    if extra:
        claims.update(extra)
    return claims


def create_access_token(
    *,
    subject: str,
    public_id: str,
    role: str,
    permissions: list[str],
) -> str:
    """Issue a signed JWT access token with full RBAC claims.

    Args:
        subject:     User internal ID (string-cast int).
        public_id:   User UUID string for external reference.
        role:        Role name (e.g., "ADMIN", "ODS_OPERATOR").
        permissions: List of permission codes for this role.

    Returns:
        Signed JWT string valid for ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = _base_claims(
        subject=subject,
        public_id=public_id,
        token_type="access",
        expire=expire,
        extra={"role": role, "permissions": permissions},
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    *,
    subject: str,
    public_id: str,
) -> tuple[str, str]:
    """Issue a signed JWT refresh token.

    Returns:
        Tuple of (signed_token, jti) — the jti must be stored in RefreshSession.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload = _base_claims(
        subject=subject,
        public_id=public_id,
        token_type="refresh",
        expire=expire,
    )
    payload["jti"] = jti  # Override the auto-generated one with the one we'll store.
    return (
        jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm),
        jti,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token signature and expiry.

    Does NOT check revocation — callers must verify the jti against the DB.

    Raises:
        AuthenticationError: If the token is expired or signature is invalid.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc
    return payload
