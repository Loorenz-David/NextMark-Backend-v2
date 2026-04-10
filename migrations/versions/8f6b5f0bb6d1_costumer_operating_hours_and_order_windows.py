"""costumer + operating hours + order delivery windows

Revision ID: 8f6b5f0bb6d1
Revises: cf4d2e8a91b3
Create Date: 2026-03-02 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "8f6b5f0bb6d1"
down_revision = "cf4d2e8a91b3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "costumer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("external_source", sa.String(), nullable=True),
        sa.Column("external_costumer_id", sa.String(), nullable=True),
        sa.Column("default_address_id", sa.Integer(), nullable=True),
        sa.Column("default_primary_phone_id", sa.Integer(), nullable=True),
        sa.Column("default_secondary_phone_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_costumer_first_name", "costumer", ["first_name"], unique=False)
    op.create_index("ix_costumer_last_name", "costumer", ["last_name"], unique=False)
    op.create_index("ix_costumer_email", "costumer", ["email"], unique=False)
    op.create_index("ix_costumer_external_source", "costumer", ["external_source"], unique=False)
    op.create_index("ix_costumer_external_costumer_id", "costumer", ["external_costumer_id"], unique=False)
    op.create_index("ix_costumer_team_id", "costumer", ["team_id"], unique=False)
    op.create_index("ix_costumer_team_id_email", "costumer", ["team_id", "email"], unique=False)
    op.create_index("ix_costumer_team_id_last_name", "costumer", ["team_id", "last_name"], unique=False)

    op.create_table(
        "costumer_address",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("costumer_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "address",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["costumer_id"], ["costumer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_costumer_address_costumer_id", "costumer_address", ["costumer_id"], unique=False)
    if is_postgres:
        op.create_index(
            "ix_costumer_address_address_gin",
            "costumer_address",
            ["address"],
            unique=False,
            postgresql_using="gin",
        )

    op.create_table(
        "costumer_phone",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("costumer_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "phone",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("phone_type", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["costumer_id"], ["costumer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_costumer_phone_costumer_id", "costumer_phone", ["costumer_id"], unique=False)
    if is_postgres:
        op.create_index(
            "ix_costumer_phone_phone_gin",
            "costumer_phone",
            ["phone"],
            unique=False,
            postgresql_using="gin",
        )

    op.create_table(
        "costumer_operating_hours",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("costumer_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("open_time", sa.String(length=5), nullable=False),
        sa.Column("close_time", sa.String(length=5), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["costumer_id"], ["costumer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("costumer_id", "weekday", name="uq_costumer_operating_hours_weekday"),
    )
    op.create_index(
        "ix_costumer_operating_hours_costumer_id",
        "costumer_operating_hours",
        ["costumer_id"],
        unique=False,
    )

    with op.batch_alter_table("costumer", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_costumer_default_address_id_costumer_address",
            "costumer_address",
            ["default_address_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_costumer_default_primary_phone_id_costumer_phone",
            "costumer_phone",
            ["default_primary_phone_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_costumer_default_secondary_phone_id_costumer_phone",
            "costumer_phone",
            ["default_secondary_phone_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.add_column(sa.Column("costumer_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_order_costumer_id", ["costumer_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_order_costumer_id_costumer",
            "costumer",
            ["costumer_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "order_delivery_window",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_delivery_window_order_id", "order_delivery_window", ["order_id"], unique=False)
    op.create_index("ix_order_delivery_window_start_at", "order_delivery_window", ["start_at"], unique=False)
    op.create_index("ix_order_delivery_window_end_at", "order_delivery_window", ["end_at"], unique=False)
    op.create_index(
        "ix_order_delivery_window_order_id_start_at",
        "order_delivery_window",
        ["order_id", "start_at"],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("ix_order_delivery_window_order_id_start_at", table_name="order_delivery_window")
    op.drop_index("ix_order_delivery_window_end_at", table_name="order_delivery_window")
    op.drop_index("ix_order_delivery_window_start_at", table_name="order_delivery_window")
    op.drop_index("ix_order_delivery_window_order_id", table_name="order_delivery_window")
    op.drop_table("order_delivery_window")

    with op.batch_alter_table("order", schema=None) as batch_op:
        batch_op.drop_constraint("fk_order_costumer_id_costumer", type_="foreignkey")
        batch_op.drop_index("ix_order_costumer_id")
        batch_op.drop_column("costumer_id")

    with op.batch_alter_table("costumer", schema=None) as batch_op:
        batch_op.drop_constraint("fk_costumer_default_secondary_phone_id_costumer_phone", type_="foreignkey")
        batch_op.drop_constraint("fk_costumer_default_primary_phone_id_costumer_phone", type_="foreignkey")
        batch_op.drop_constraint("fk_costumer_default_address_id_costumer_address", type_="foreignkey")

    op.drop_index("ix_costumer_operating_hours_costumer_id", table_name="costumer_operating_hours")
    op.drop_table("costumer_operating_hours")

    if is_postgres:
        op.drop_index("ix_costumer_phone_phone_gin", table_name="costumer_phone")
    op.drop_index("ix_costumer_phone_costumer_id", table_name="costumer_phone")
    op.drop_table("costumer_phone")

    if is_postgres:
        op.drop_index("ix_costumer_address_address_gin", table_name="costumer_address")
    op.drop_index("ix_costumer_address_costumer_id", table_name="costumer_address")
    op.drop_table("costumer_address")

    op.drop_index("ix_costumer_team_id_last_name", table_name="costumer")
    op.drop_index("ix_costumer_team_id_email", table_name="costumer")
    op.drop_index("ix_costumer_team_id", table_name="costumer")
    op.drop_index("ix_costumer_external_costumer_id", table_name="costumer")
    op.drop_index("ix_costumer_external_source", table_name="costumer")
    op.drop_index("ix_costumer_email", table_name="costumer")
    op.drop_index("ix_costumer_last_name", table_name="costumer")
    op.drop_index("ix_costumer_first_name", table_name="costumer")
    op.drop_table("costumer")

