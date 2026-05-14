"""backup module — backup_configs + backup_jobs

Revision ID: 0074
Revises: 0073
Create Date: 2026-05-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0074"
down_revision: Union[str, None] = "0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backup_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("backup_type", sa.String(20), nullable=False, server_default="platform"),
        sa.Column("destination", sa.String(20), nullable=False, server_default="local"),
        sa.Column("schedule_cron", sa.String(50), nullable=True),
        sa.Column("retention_count", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("local_path", sa.String(500), nullable=True),
        sa.Column("s3_bucket", sa.String(255), nullable=True),
        sa.Column("s3_prefix", sa.String(255), nullable=True),
        sa.Column("s3_region", sa.String(50), nullable=True),
        sa.Column("s3_credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("sftp_host", sa.String(255), nullable=True),
        sa.Column("sftp_port", sa.Integer(), nullable=True, server_default="22"),
        sa.Column("sftp_user", sa.String(100), nullable=True),
        sa.Column("sftp_credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("sftp_path", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_backup_configs_tenant_id", "backup_configs", ["tenant_id"])

    op.create_table(
        "backup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("backup_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("backup_type", sa.String(20), nullable=False, server_default="platform"),
        sa.Column("destination", sa.String(20), nullable=False, server_default="local"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_backup_jobs_config_id", "backup_jobs", ["config_id"])
    op.create_index("ix_backup_jobs_tenant_id", "backup_jobs", ["tenant_id"])
    op.create_index("ix_backup_jobs_created_at", "backup_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_backup_jobs_created_at", "backup_jobs")
    op.drop_index("ix_backup_jobs_tenant_id", "backup_jobs")
    op.drop_index("ix_backup_jobs_config_id", "backup_jobs")
    op.drop_table("backup_jobs")
    op.drop_index("ix_backup_configs_tenant_id", "backup_configs")
    op.drop_table("backup_configs")
