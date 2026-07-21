"""Admin domain Pydantic schemas — request/response models for user administration."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserListOut(BaseModel):
    """Lightweight user row for the admin Users table."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    full_name: str
    username: str
    email: Optional[str] = None
    role_name: str
    role_public_id: uuid.UUID
    warehouse_name: Optional[str] = None
    warehouse_public_id: Optional[uuid.UUID] = None
    is_active: bool
    is_locked: bool
    must_change_password: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime


class UserAdminOut(BaseModel):
    """Full admin view of a user (returned on GET /admin/users/:id)."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    full_name: str
    username: str
    email: Optional[str] = None
    role_name: str
    role_public_id: uuid.UUID
    warehouse_name: Optional[str] = None
    warehouse_public_id: Optional[uuid.UUID] = None
    is_active: bool
    is_locked: bool
    failed_login_count: int
    locked_until: Optional[datetime] = None
    must_change_password: bool
    password_changed_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: list[str]


class CreateUserAdminRequest(BaseModel):
    """Admin payload to create a new user."""

    username: str = Field(..., min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: str = Field(..., min_length=1, max_length=255)

    role_public_id: uuid.UUID
    warehouse_public_id: Optional[uuid.UUID] = None


class UpdateUserAdminRequest(BaseModel):
    """Admin payload to edit a user. Password is never included."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=255)

    role_public_id: Optional[uuid.UUID] = None
    warehouse_public_id: Optional[uuid.UUID] = None  # pass null explicitly to unassign
    is_active: Optional[bool] = None


class ResetPasswordResponse(BaseModel):
    """Returned once after a password reset. Temporary password must be saved immediately."""

    temporary_password: str
    message: str = "Temporary password generated. User must change it on next login."


class RoleOut(BaseModel):
    """Role row for dropdowns."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    name: str
