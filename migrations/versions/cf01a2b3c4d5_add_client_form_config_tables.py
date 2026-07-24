"""add client form configuration tables

Creates the per-team public client-form configuration: settings singleton,
immutable terms versions, ordered rules, and placed media. Adds the two order
columns recording which terms version the customer accepted.

Revision ID: cf01a2b3c4d5
Revises: 56bd2bef4cf9
Create Date: 2026-07-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from Delivery_app_BK.models.utils import UTCDateTime

revision = "cf01a2b3c4d5"
down_revision = "56bd2bef4cf9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_form_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("terms_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("require_acceptance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("show_rules", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("show_media", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", name="uq_client_form_settings_team"),
    )
    op.create_index(
        op.f("ix_client_form_settings_client_id"), "client_form_settings", ["client_id"]
    )

    op.create_table(
        "client_form_terms_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", JSONB().with_variant(sa.JSON, "sqlite"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_id", "version_number", name="uq_client_form_terms_version_team_version"
        ),
    )
    op.create_index(
        op.f("ix_client_form_terms_version_team_id"), "client_form_terms_version", ["team_id"]
    )
    op.create_index(
        "ix_client_form_terms_team_created",
        "client_form_terms_version",
        ["team_id", "created_at"],
    )
    # At most one active terms version per team.
    op.create_index(
        "uix_client_form_terms_active_team",
        "client_form_terms_version",
        ["team_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )

    op.create_table(
        "client_form_rule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "position", name="uq_client_form_rule_team_position"),
    )
    op.create_index(op.f("ix_client_form_rule_client_id"), "client_form_rule", ["client_id"])

    op.create_table(
        "client_form_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("placement", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=True),
        sa.Column("alt_text", sa.String(), nullable=True),
        sa.Column("link_url", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "team_id",
            "placement",
            "position",
            name="uq_client_form_media_team_placement_position",
        ),
    )
    op.create_index(op.f("ix_client_form_media_client_id"), "client_form_media", ["client_id"])
    op.create_index(op.f("ix_client_form_media_placement"), "client_form_media", ["placement"])

    op.add_column("order", sa.Column("accepted_terms_version_id", sa.Integer(), nullable=True))
    op.add_column("order", sa.Column("terms_accepted_at", UTCDateTime(), nullable=True))
    op.create_foreign_key(
        "fk_order_accepted_terms_version",
        "order",
        "client_form_terms_version",
        ["accepted_terms_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_order_accepted_terms_version", "order", type_="foreignkey")
    op.drop_column("order", "terms_accepted_at")
    op.drop_column("order", "accepted_terms_version_id")

    op.drop_index(op.f("ix_client_form_media_placement"), table_name="client_form_media")
    op.drop_index(op.f("ix_client_form_media_client_id"), table_name="client_form_media")
    op.drop_table("client_form_media")

    op.drop_index(op.f("ix_client_form_rule_client_id"), table_name="client_form_rule")
    op.drop_table("client_form_rule")

    op.drop_index(
        "uix_client_form_terms_active_team", table_name="client_form_terms_version"
    )
    op.drop_index(
        "ix_client_form_terms_team_created", table_name="client_form_terms_version"
    )
    op.drop_index(
        op.f("ix_client_form_terms_version_team_id"), table_name="client_form_terms_version"
    )
    op.drop_table("client_form_terms_version")

    op.drop_index(
        op.f("ix_client_form_settings_client_id"), table_name="client_form_settings"
    )
    op.drop_table("client_form_settings")
