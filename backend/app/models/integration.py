import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class IntegrationType(str, enum.Enum):
    shodan     = "shodan"
    wazuh      = "wazuh"
    openvas    = "openvas"
    nmap       = "nmap"
    zabbix     = "zabbix"
    bookstack  = "bookstack"


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    type: Mapped[IntegrationType] = mapped_column(
        Enum(IntegrationType, native_enum=False), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    encrypted_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
