"""ORM models para F36 — Governança de Identidade AD/M365."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class IdentityConnector(Base):
    __tablename__ = "identity_connectors"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ad_ldap")
    config_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    users: Mapped[list["AdUser"]] = relationship("AdUser", back_populates="connector", lazy="select")
    groups: Mapped[list["AdGroup"]] = relationship("AdGroup", back_populates="connector", lazy="select")


class AdUser(Base):
    __tablename__ = "ad_users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    connector_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("identity_connectors.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ad_ldap")
    object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    upn: Mapped[str] = mapped_column(String(300), nullable=False)
    sam_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    manager_upn: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_registered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_sign_in: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    password_last_set: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at_ad: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    license_skus: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    connector: Mapped["IdentityConnector"] = relationship("IdentityConnector", back_populates="users", lazy="select")
    memberships: Mapped[list["AdGroupMembership"]] = relationship("AdGroupMembership", back_populates="user", lazy="select", cascade="all, delete-orphan")
    sod_violations: Mapped[list["SodViolation"]] = relationship("SodViolation", back_populates="user", lazy="select", cascade="all, delete-orphan")
    review_tasks: Mapped[list["AccessReviewTask"]] = relationship("AccessReviewTask", back_populates="subject_user", lazy="select")


class AdGroup(Base):
    __tablename__ = "ad_groups"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    connector_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("identity_connectors.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="ad_ldap")
    object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    dn: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    owner_upns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    health_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    health_issues: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    connector: Mapped["IdentityConnector"] = relationship("IdentityConnector", back_populates="groups", lazy="select")
    memberships: Mapped[list["AdGroupMembership"]] = relationship("AdGroupMembership", back_populates="group", lazy="select", cascade="all, delete-orphan")
    jit_requests: Mapped[list["JitRequest"]] = relationship("JitRequest", back_populates="target_group", lazy="select")


class AdGroupMembership(Base):
    __tablename__ = "ad_group_memberships"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ad_users.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ad_groups.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["AdUser"] = relationship("AdUser", back_populates="memberships", lazy="select")
    group: Mapped["AdGroup"] = relationship("AdGroup", back_populates="memberships", lazy="select")


class SodRule(Base):
    __tablename__ = "sod_rules"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_a_type: Mapped[str] = mapped_column(String(30), nullable=False, default="group")
    role_a_name: Mapped[str] = mapped_column(String(300), nullable=False)
    role_b_type: Mapped[str] = mapped_column(String(30), nullable=False, default="group")
    role_b_name: Mapped[str] = mapped_column(String(300), nullable=False)
    risk_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="high")
    remediation_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    violations: Mapped[list["SodViolation"]] = relationship("SodViolation", back_populates="rule", lazy="select", cascade="all, delete-orphan")


class SodViolation(Base):
    __tablename__ = "sod_violations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ad_users.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("sod_rules.id", ondelete="CASCADE"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    accepted_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    user: Mapped["AdUser"] = relationship("AdUser", back_populates="sod_violations", lazy="select")
    rule: Mapped["SodRule"] = relationship("SodRule", back_populates="violations", lazy="select")


class AccessCampaign(Base):
    __tablename__ = "access_campaigns"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    campaign_type: Mapped[str] = mapped_column(String(30), nullable=False, default="by_manager")
    scope_filter: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reviewer_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manager")
    deadline: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    recurrence: Mapped[str] = mapped_column(String(20), nullable=False, default="once")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    tasks: Mapped[list["AccessReviewTask"]] = relationship("AccessReviewTask", back_populates="campaign", lazy="select", cascade="all, delete-orphan")


class AccessReviewTask(Base):
    __tablename__ = "access_review_tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("access_campaigns.id", ondelete="CASCADE"), nullable=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    subject_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ad_users.id", ondelete="CASCADE"), nullable=False)
    access_item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="group")
    access_item_name: Mapped[str] = mapped_column(String(300), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    campaign: Mapped["AccessCampaign | None"] = relationship("AccessCampaign", back_populates="tasks", lazy="select")
    subject_user: Mapped["AdUser"] = relationship("AdUser", back_populates="review_tasks", lazy="select")


class JitRequest(Base):
    __tablename__ = "jit_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_group_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ad_groups.id", ondelete="SET NULL"), nullable=True)
    target_group_name: Mapped[str] = mapped_column(String(300), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    approver_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    target_group: Mapped["AdGroup | None"] = relationship("AdGroup", back_populates="jit_requests", lazy="select")
