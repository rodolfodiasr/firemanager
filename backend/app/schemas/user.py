from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.operator


class UserRead(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    mfa_enabled: bool
    is_super_admin: bool = False

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class TenantInfo(BaseModel):
    id: str
    name: str
    slug: str


class TokenResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    pre_token: str | None = None
    tenants: list[TenantInfo] | None = None
    token_type: str = "bearer"


class MFASetupResponse(BaseModel):
    secret: str
    qr_uri: str


class MFAVerifyRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=6)
