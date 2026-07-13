"""Standard API response envelope helpers.

Every endpoint must return one of these two shapes:

Success:
    {
        "success": true,
        "data": <any>,
        "meta": <pagination | null>,
        "message": "Optional human message."
    }

Failure (handled by AppExceptionMiddleware, not directly in routes):
    {
        "success": false,
        "code": "INV_004",
        "message": "Insufficient inventory.",
        "details": {}
    }
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class PaginationMeta(BaseModel):
    """Pagination metadata attached to list responses."""

    page: int
    page_size: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[DataT]):
    """Generic success envelope returned by all endpoints."""

    success: bool = True
    data: DataT
    meta: PaginationMeta | None = None
    message: str = ""


def ok(
    data: Any,
    message: str = "",
    meta: PaginationMeta | None = None,
) -> dict[str, Any]:
    """Build a success envelope dict for use in route return statements."""
    return {
        "success": True,
        "data": data,
        "meta": meta.model_dump() if meta else None,
        "message": message,
    }


def paginate(
    data: Any,
    page: int,
    page_size: int,
    total: int,
) -> dict[str, Any]:
    """Build a paginated success envelope."""
    import math

    return ok(
        data=data,
        meta=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 1,
        ),
    )
