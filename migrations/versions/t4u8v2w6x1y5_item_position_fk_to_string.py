"""Change item position from FK to string label."""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "t4u8v2w6x1y5"
down_revision = ("68565fdc3a1b", "s4t8u2v6w1x9")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("item", sa.Column("item_position", sa.String(), nullable=True))
    op.create_index(op.f("ix_item_item_position"), "item", ["item_position"], unique=False)

    op.execute(
        """
        UPDATE item
        SET item_position = ip.name
        FROM item_position AS ip
        WHERE item.item_position_id = ip.id
        """
    )

    op.drop_constraint("item_item_position_id_fkey", "item", type_="foreignkey")
    op.drop_column("item", "item_position_id")


def downgrade():
    op.add_column("item", sa.Column("item_position_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE item
        SET item_position_id = ip.id
        FROM item_position AS ip
        WHERE item.item_position = ip.name
          AND ip.team_id = item.team_id
        """
    )

    op.create_foreign_key(
        "item_item_position_id_fkey",
        "item",
        "item_position",
        ["item_position_id"],
        ["id"],
    )
    op.drop_index(op.f("ix_item_item_position"), table_name="item")
    op.drop_column("item", "item_position")
