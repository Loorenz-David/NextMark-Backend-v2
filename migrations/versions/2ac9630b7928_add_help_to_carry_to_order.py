"""add help_to_carry to order

Revision ID: 2ac9630b7928
Revises: d2f4a6c8e9b1
Create Date: 2026-05-17 13:52:01.107302

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2ac9630b7928"
down_revision = "d2f4a6c8e9b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "order",
        sa.Column("help_to_carry", sa.Boolean(), nullable=True),
    )


def downgrade():
    op.drop_column("order", "help_to_carry")
