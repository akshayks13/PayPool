"""Baseline durable domain records; preserves existing local installations."""

import sqlalchemy as sa
from alembic import op

revision = "0001_commerce_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("paypool_records"):
        op.create_table(
            "paypool_records",
            sa.Column("kind", sa.String(40), primary_key=True),
            sa.Column("id", sa.String(100), primary_key=True),
            sa.Column("data", sa.JSON(), nullable=False),
        )


def downgrade():
    raise RuntimeError(
        "Refusing to drop durable commerce records; restore a reviewed backup instead"
    )
