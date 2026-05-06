"""device: add zabbix_host_name and wazuh_agent_name for precise cross-system correlation

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("zabbix_host_name", sa.String(255), nullable=True))
    op.add_column("devices", sa.Column("wazuh_agent_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "wazuh_agent_name")
    op.drop_column("devices", "zabbix_host_name")
