import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, String, TIMESTAMP, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class AuthSource(str, enum.Enum):
    local = "local"          # senha bcrypt armazenada na plataforma
    ldap = "ldap"            # bind no AD local via LDAP
    oidc = "oidc"            # Azure AD / Okta / Google via OIDC
    break_glass = "break_glass"  # conta local de emergência — bypassa sso_required


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), nullable=False, default=UserRole.operator)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Autenticação mista ────────────────────────────────────────────────────
    auth_source: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    ldap_dn: Mapped[str | None] = mapped_column(Text, nullable=True)
    break_glass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
