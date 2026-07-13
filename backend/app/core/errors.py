"""Standardized error hierarchy for the FMCG WMS application.

All domain exceptions extend AppError, which carries a human-readable
message and a machine-readable error code string (e.g., "INV_004").
The global exception handler in app.core.middleware translates these
into the standard API envelope.
"""

from http import HTTPStatus


class AppError(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "APP_000"

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


# ---------------------------------------------------------------------------
# 400 Bad Request
# ---------------------------------------------------------------------------


class ValidationError(AppError):
    status_code = HTTPStatus.BAD_REQUEST
    code = "VAL_001"


class ExcelTemplateError(AppError):
    """Raised when an uploaded Excel file does not match the expected template."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "XLS_001"


# ---------------------------------------------------------------------------
# 401 / 403 Auth
# ---------------------------------------------------------------------------


class AuthenticationError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTH_001"


class AccountLockedError(AppError):
    """Raised when a user account is locked due to repeated failed login attempts."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTH_003"

    def __init__(self, minutes_remaining: int = 0) -> None:
        super().__init__(
            message=f"Account is temporarily locked. Try again in {minutes_remaining} minute(s).",
            details={"minutes_remaining": minutes_remaining},
        )


class PermissionDeniedError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "AUTH_002"


class TokenRevokedError(AppError):
    """Raised when a refresh token has been explicitly revoked (logout)."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTH_004"


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "NF_001"


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------


class OptimisticLockError(AppError):
    """Raised when a stale `version` field is detected during an update."""

    status_code = HTTPStatus.CONFLICT
    code = "LOCK_001"

    def __init__(self) -> None:
        super().__init__(
            message="Record was modified by another user. Please refresh and try again.",
            details={},
        )


class DuplicateError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "DUP_001"


# ---------------------------------------------------------------------------
# 422 Inventory / Business
# ---------------------------------------------------------------------------


class InsufficientInventoryError(AppError):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "INV_001"


class InvalidStateTransitionError(AppError):
    """Raised when a request status machine receives an illegal transition."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "REQ_001"
