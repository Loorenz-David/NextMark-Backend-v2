"""add title and description to client form media

Lets a media item carry a visible caption alongside the image and link, so a
placement can render a titled card rather than a bare banner. Both are nullable:
the image remains the only required part.

Revision ID: cf02b3c4d5e6
Revises: cf01a2b3c4d5
Create Date: 2026-07-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "cf02b3c4d5e6"
down_revision = "cf01a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_form_media", sa.Column("title", sa.String(), nullable=True))
    op.add_column("client_form_media", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("client_form_media", "description")
    op.drop_column("client_form_media", "title")
