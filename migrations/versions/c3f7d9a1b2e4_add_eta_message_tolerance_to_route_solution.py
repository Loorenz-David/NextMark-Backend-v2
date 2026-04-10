"""add eta message tolerance to route solution

Revision ID: c3f7d9a1b2e4
Revises: de054463773c
Create Date: 2026-04-10 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c3f7d9a1b2e4"
down_revision = "de054463773c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "route_solution",
        sa.Column(
            "eta_message_tolerance",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("1800"),
        ),
    )
    op.execute(
        """
        UPDATE route_solution
        SET eta_message_tolerance = 1800
        WHERE eta_message_tolerance IS NULL
        """
    )
    with op.batch_alter_table("route_solution", schema=None) as batch_op:
        batch_op.alter_column(
            "eta_message_tolerance",
            server_default=None,
            existing_type=sa.Integer(),
        )


def downgrade() -> None:
    op.drop_column("route_solution", "eta_message_tolerance")
