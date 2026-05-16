"""0087 — RMM: coluna site_filter em rmm_integrations para filtrar agentes por site/cliente."""
from alembic import op
import sqlalchemy as sa

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rmm_integrations", sa.Column("site_filter", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("rmm_integrations", "site_filter")
