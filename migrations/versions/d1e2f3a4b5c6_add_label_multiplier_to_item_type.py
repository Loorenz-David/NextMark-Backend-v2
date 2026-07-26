"""add label_multiplier to item_type

Lets an item type carry how many labels should be printed per item, so the
frontend can drive a label printer with the right copy count. Non-nullable with a
server default of 1 so existing types keep printing a single label.

Revision ID: d1e2f3a4b5c6
Revises: cf02b3c4d5e6
Create Date: 2026-07-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "cf02b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("item_type", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "label_multiplier",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("item_type", schema=None) as batch_op:
        batch_op.drop_column("label_multiplier")
