"""Auth domain Pydantic schemas — request bodies and response shapes."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Payload for POST /auth/login.

    `identifier` accepts either a username or an email address.
    """

    identifier: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Username or email address.",
        examples=["admin", "admin@plant.local"],
    )
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    """Access and refresh tokens returned on successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    permissions: list[str] = Field(default_factory=list)


class RefreshRequest(BaseModel):
    """Payload for POST /auth/refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Payload for POST /auth/logout."""

    refresh_token: str


class UserOut(BaseModel):
    """Public representation of a user returned by the API."""

    model_config = {"from_attributes": True}

    public_id: uuid.UUID
    username: str
    email: str
    full_name: str
    is_active: bool
    role_name: str
    permissions: list[str]

    @classmethod
    def from_orm_user(cls, user: object) -> "UserOut":
        """Construct UserOut from a User ORM instance."""
        from app.domains.auth.models import User as UserModel

        assert isinstance(user, UserModel)
        perms = [rp.permission.code for rp in user.role.permissions]
        return cls(
            public_id=user.public_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            role_name=user.role.name,
            permissions=perms,
        )


class CreateUserRequest(BaseModel):
    """Admin payload to create a new system user."""

    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters.",
    )
    role_public_id: uuid.UUID
