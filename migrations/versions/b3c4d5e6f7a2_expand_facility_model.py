"""expand facility model with typed operational columns

Revision ID: b3c4d5e6f7a2
Revises: a2b3c4d5e6f7
Create Date: 2026-03-29 12:05:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3c4d5e6f7a2"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "facility",
        sa.Column("facility_type", sa.String(), nullable=False, server_default="warehouse"),
    )
    op.add_column(
        "facility",
        sa.Column("can_dispatch", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "facility",
        sa.Column("can_receive_returns", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "facility",
        sa.Column(
            "operating_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "facility",
        sa.Column(
            "default_loading_time_seconds",
            sa.Integer(),
            nullable=False,
            server_default="600",
        ),
    )
    op.add_column(
        "facility",
        sa.Column(
            "default_unloading_time_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
    )
    op.add_column(
        "facility",
        sa.Column("max_orders_per_day", sa.Integer(), nullable=True),
    )
    op.add_column(
        "facility",
        sa.Column(
            "external_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.create_index("ix_facility_facility_type", "facility", ["team_id", "facility_type"])
    op.create_index("ix_facility_can_dispatch", "facility", ["team_id", "can_dispatch"])


def downgrade():
    op.drop_index("ix_facility_can_dispatch", table_name="facility")
    op.drop_index("ix_facility_facility_type", table_name="facility")
    op.drop_column("facility", "external_refs")
    op.drop_column("facility", "max_orders_per_day")
    op.drop_column("facility", "default_unloading_time_seconds")
    op.drop_column("facility", "default_loading_time_seconds")
    op.drop_column("facility", "operating_hours")
    op.drop_column("facility", "can_receive_returns")
    op.drop_column("facility", "can_dispatch")
    op.drop_column("facility", "facility_type")
