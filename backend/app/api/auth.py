from datetime import datetime, timedelta, timezone
from typing import Annotated, NamedTuple
from uuid import UUID

import bcrypt
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_role import TenantRole, UserTenantRole
from app.schemas.user import (
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    PasswordChange,
    TenantInfo,
    TokenResponse,
    UserCreate,
    UserRead,
)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ALGORITHM = "HS256"
PRE_TOKEN_TTL = timedelta(minutes=5)


# ── Token helpers ─────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def _create_access_token(user: User, tenant_id: UUID | None, role: str | None) -> str:
    payload: dict = {
        "sub":   str(user.id),
        "super": user.is_super_admin,
    }
    if tenant_id:
        payload["tenant_id"] = str(tenant_id)
    if role:
        payload["role"] = role
    return _create_token(payload, timedelta(minutes=settings.access_token_expire_minutes))


def _create_refresh_token(user_id: UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.refresh_token_expire_days),
    )


def _create_pre_token(user_id: UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "pre_tenant"},
        PRE_TOKEN_TTL,
    )


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependencies ──────────────────────────────────────────────────────────────

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = _decode_token(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user


class TenantContext(NamedTuple):
    user:   User
    tenant: Tenant
    role:   TenantRole


async def get_tenant_context(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> TenantContext:
    payload = _decode_token(token)

    user_id   = payload.get("sub")
    tenant_id = payload.get("tenant_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Nenhum tenant selecionado")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    result = await db.execute(select(Tenant).where(Tenant.id == UUID(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="Tenant não encontrado ou inativo")

    # Support mode: super admin issued a read-only token for this tenant
    if payload.get("support") and user.is_super_admin:
        return TenantContext(user=user, tenant=tenant, role=TenantRole.readonly)

    result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == tenant.id,
        )
    )
    utr = result.scalar_one_or_none()
    if not utr:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    return TenantContext(user=user, tenant=tenant, role=utr.role)


async def require_super_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    db:    Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = _decode_token(token)
    if not payload.get("super"):
        raise HTTPException(status_code=403, detail="Requer privilégio de Super Admin")
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Requer privilégio de Super Admin")
    return user


async def require_tenant_admin(ctx: Annotated[TenantContext, Depends(get_tenant_context)]) -> TenantContext:
    if ctx.role != TenantRole.admin:
        raise HTTPException(status_code=403, detail="Requer papel de administrador no tenant")
    return ctx


async def resolve_tenant_access(token: str, tenant_id: UUID, db: AsyncSession) -> TenantContext:
    """Super admin OR tenant admin can access the given tenant's members."""
    payload = _decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    if payload.get("super") and user.is_super_admin:
        return TenantContext(user=user, tenant=tenant, role=TenantRole.admin)

    jwt_tenant_id = payload.get("tenant_id")
    if not jwt_tenant_id or UUID(jwt_tenant_id) != tenant_id:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    result = await db.execute(
        select(UserTenantRole).where(
            UserTenantRole.user_id == user.id,
            UserTenantRole.tenant_id == tenant.id,
        )
    )
    utr = result.scalar_one_or_none()
    if not utr or utr.role != TenantRole.admin:
        raise HTTPException(status_code=403, detail="Requer papel de administrador no tenant")

    return TenantContext(user=user, tenant=tenant, role=utr.role)


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=data.email,
        name=data.name,
        hashed_password=_hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.mfa_enabled:
        if not data.totp_code:
            raise HTTPException(status_code=401, detail="MFA code required")
        totp = pyotp.TOTP(user.mfa_secret or "")
        if not totp.verify(data.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    # Super admin — no tenant needed
    if user.is_super_admin:
        access_token = _create_access_token(user, tenant_id=None, role="super_admin")
        return TokenResponse(
            access_token=access_token,
            refresh_token=_create_refresh_token(user.id),
        )

    # Fetch tenants for this user
    utr_result = await db.execute(
        select(UserTenantRole, Tenant)
        .join(Tenant, UserTenantRole.tenant_id == Tenant.id)
        .where(UserTenantRole.user_id == user.id, Tenant.is_active == True)
    )
    rows = utr_result.all()

    if not rows:
        raise HTTPException(status_code=403, detail="Usuário não associado a nenhum tenant ativo")

    if len(rows) == 1:
        utr, tenant = rows[0]
        access_token = _create_access_token(user, tenant_id=tenant.id, role=utr.role.value)
        return TokenResponse(
            access_token=access_token,
            refresh_token=_create_refresh_token(user.id),
        )

    # Multiple tenants — return pre_token + list
    return TokenResponse(
        pre_token=_create_pre_token(user.id),
        tenants=[TenantInfo(id=str(tenant.id), name=tenant.name, slug=tenant.slug) for _, tenant in rows],
    )


@router.post("/select-tenant", response_model=TokenResponse)
async def select_tenant(
    body: dict,
    db:   Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    pre_token  = body.get("pre_token", "")
    tenant_id  = body.get("tenant_id", "")

    payload = _decode_token(pre_token)
    if payload.get("type") != "pre_tenant":
        raise HTTPException(status_code=400, detail="Token inválido para seleção de tenant")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuário inválido")

    tid = UUID(tenant_id)
    result = await db.execute(
        select(UserTenantRole, Tenant)
        .join(Tenant, UserTenantRole.tenant_id == Tenant.id)
        .where(UserTenantRole.user_id == user.id, UserTenantRole.tenant_id == tid)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=403, detail="Sem acesso a este tenant")

    utr, tenant = row
    access_token = _create_access_token(user, tenant_id=tenant.id, role=utr.role.value)
    return TokenResponse(
        access_token=access_token,
        refresh_token=_create_refresh_token(user.id),
    )


@router.get("/me/tenants", response_model=list[TenantInfo])
async def list_my_tenants(
    current_user: Annotated[User, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
) -> list[TenantInfo]:
    result = await db.execute(
        select(Tenant)
        .join(UserTenantRole, UserTenantRole.tenant_id == Tenant.id)
        .where(UserTenantRole.user_id == current_user.id, Tenant.is_active == True)
    )
    tenants = result.scalars().all()
    return [TenantInfo(id=str(t.id), name=t.name, slug=t.slug) for t in tenants]


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MFASetupResponse:
    secret = pyotp.random_base32()
    current_user.mfa_secret = secret
    await db.flush()
    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(name=current_user.email, issuer_name="FireManager")
    return MFASetupResponse(secret=secret, qr_uri=qr_uri)


@router.post("/mfa/verify")
async def verify_mfa(
    data: MFAVerifyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, bool]:
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA not set up")
    totp = pyotp.TOTP(current_user.mfa_secret)
    if not totp.verify(data.totp_code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.mfa_enabled = True
    await db.flush()
    return {"mfa_enabled": True}


@router.post("/me/password", status_code=204)
async def change_password(
    data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if not _verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    current_user.hashed_password = _hash_password(data.new_password)
    await db.flush()


@router.get("/me", response_model=UserRead)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
