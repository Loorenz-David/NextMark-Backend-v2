"""add cursor indexes for order and plan

Revision ID: c9d8a72e4b11
Revises: f6a9130d4c2b
Create Date: 2026-03-08 19:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c9d8a72e4b11"
down_revision = "f6a9130d4c2b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_order_creation_date_id_desc ON "order" (creation_date DESC, id DESC)'
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_delivery_plan_created_at_id_desc ON delivery_plan (created_at DESC, id DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_delivery_plan_created_at_id_desc")
    op.execute("DROP INDEX IF EXISTS ix_order_creation_date_id_desc")
