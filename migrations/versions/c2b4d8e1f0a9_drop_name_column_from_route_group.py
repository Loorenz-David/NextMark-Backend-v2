"""drop_name_column_from_route_group

Revision ID: c2b4d8e1f0a9
Revises: 9e2c1b7a4d5f
Create Date: 2026-03-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2b4d8e1f0a9"
down_revision = "9e2c1b7a4d5f"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def upgrade():
    if _has_column("route_group", "name"):
        with op.batch_alter_table("route_group", schema=None) as batch_op:
            batch_op.drop_column("name")


def downgrade():
    if not _has_column("route_group", "name"):
        with op.batch_alter_table("route_group", schema=None) as batch_op:
            batch_op.add_column(sa.Column("name", sa.String(length=255), nullable=True))
