"""added zone_color to zone model

Revision ID: 41da1fb8923e
Revises: r1t6y2u8i4o0
Create Date: 2026-04-01 11:58:17.227312

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "41da1fb8923e"
down_revision = "r1t6y2u8i4o0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("zone", schema=None) as batch_op:
        batch_op.add_column(sa.Column("zone_color", sa.String(length=7), nullable=True))


def downgrade():
    with op.batch_alter_table("zone", schema=None) as batch_op:
        batch_op.drop_column("zone_color")
