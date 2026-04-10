"""rename warehouse table to facility

Revision ID: a2b3c4d5e6f7
Revises: z1a5b9c3d7e2
Create Date: 2026-03-29 12:00:00.000000
"""

from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "z1a5b9c3d7e2"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("warehouse", "facility")
    # Rename SQLAlchemy auto-generated column indexes
    op.execute("ALTER INDEX IF EXISTS ix_warehouse_client_id RENAME TO ix_facility_client_id")
    op.execute("ALTER INDEX IF EXISTS ix_warehouse_name RENAME TO ix_facility_name")


def downgrade():
    op.execute("ALTER INDEX IF EXISTS ix_facility_name RENAME TO ix_warehouse_name")
    op.execute("ALTER INDEX IF EXISTS ix_facility_client_id RENAME TO ix_warehouse_client_id")
    op.rename_table("facility", "warehouse")
