"""add client form redirect table

Saved pages the public client form can send the customer to after a
successful submit. At most one row per team is active.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_form_redirect",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_client_form_redirect_client_id"), "client_form_redirect", ["client_id"]
    )
    op.create_index(
        "ix_client_form_redirect_team_id", "client_form_redirect", ["team_id"]
    )
    # At most one active redirect per team.
    op.create_index(
        "uix_client_form_redirect_active_team",
        "client_form_redirect",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    op.drop_index("uix_client_form_redirect_active_team", table_name="client_form_redirect")
    op.drop_index("ix_client_form_redirect_team_id", table_name="client_form_redirect")
    op.drop_index(op.f("ix_client_form_redirect_client_id"), table_name="client_form_redirect")
    op.drop_table("client_form_redirect")
