import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, Text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class VariableType(str, enum.Enum):
    string    = "string"     # texto genérico
    network   = "network"    # CIDR: 192.168.1.0/24
    ip        = "ip"         # IP único: 192.168.1.1
    port      = "port"       # porta: 443
    interface = "interface"  # nome de interface: lan, wan, port1
    zone      = "zone"       # zona/VLAN: LAN, WAN, DMZ
    hostname  = "hostname"   # FQDN: server.empresa.local
    gateway   = "gateway"    # gateway padrão: 192.168.1.1


class TenantVariable(Base):
    """Variável global do tenant — herdada por todos os devices."""
    __tablename__ = "tenant_variables"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_tenant_variable_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    variable_type: Mapped[VariableType] = mapped_column(
        Enum(VariableType, native_enum=False), nullable=False, default=VariableType.string
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DeviceVariable(Base):
    """Variável específica de um device — sobrescreve a variável de mesmo nome do tenant."""
    __tablename__ = "device_variables"
    __table_args__ = (UniqueConstraint("device_id", "name", name="uq_device_variable_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    variable_type: Mapped[VariableType] = mapped_column(
        Enum(VariableType, native_enum=False), nullable=False, default=VariableType.string
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
