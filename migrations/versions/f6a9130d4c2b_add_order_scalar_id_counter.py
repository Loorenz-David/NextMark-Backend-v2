"""add order scalar id counter

Revision ID: f6a9130d4c2b
Revises: e41b22f934ad
Create Date: 2026-03-08 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a9130d4c2b"
down_revision = "e41b22f934ad"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_scalar_counter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default=sa.text("1000")),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_order_scalar_counter_team_id"),
    )
    with op.batch_alter_table("order_scalar_counter", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_order_scalar_counter_team_id"),
            ["team_id"],
            unique=False,
        )

    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.add_column(sa.Column("order_scalar_id", sa.Integer(), nullable=True))

    op.execute(
        """
        WITH ranked_orders AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY team_id
                    ORDER BY creation_date ASC, id ASC
                ) + 999 AS scalar_id
            FROM "order"
        )
        UPDATE "order"
        SET order_scalar_id = (
            SELECT ranked_orders.scalar_id
            FROM ranked_orders
            WHERE ranked_orders.id = "order".id
        )
        """
    )

    op.execute(
        """
        INSERT INTO order_scalar_counter (team_id, next_value)
        SELECT team_id, MAX(order_scalar_id) + 1
        FROM "order"
        WHERE team_id IS NOT NULL
        GROUP BY team_id
        """
    )

    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.alter_column("order_scalar_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f("ix_order_order_scalar_id"), ["order_scalar_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_order_team_scalar_id",
            ["team_id", "order_scalar_id"],
        )

    with op.batch_alter_table("order_scalar_counter", schema=None) as batch_op:
        batch_op.alter_column("next_value", server_default=None)


def downgrade():
    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.drop_constraint("uq_order_team_scalar_id", type_="unique")
        batch_op.drop_index(batch_op.f("ix_order_order_scalar_id"))
        batch_op.drop_column("order_scalar_id")

    with op.batch_alter_table("order_scalar_counter", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_order_scalar_counter_team_id"))

    op.drop_table("order_scalar_counter")
