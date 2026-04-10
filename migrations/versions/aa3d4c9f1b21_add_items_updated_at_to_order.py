"""add items_updated_at to order

Revision ID: aa3d4c9f1b21
Revises: c9d8a72e4b11
Create Date: 2026-03-08 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa

from Delivery_app_BK.models.utils import UTCDateTime


revision = "aa3d4c9f1b21"
down_revision = "c9d8a72e4b11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order", sa.Column("items_updated_at", UTCDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("order", "items_updated_at")
