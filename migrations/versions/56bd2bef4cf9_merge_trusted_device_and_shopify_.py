"""merge trusted_device and shopify_tracking heads

Revision ID: 56bd2bef4cf9
Revises: t9u5v1w7x3y0, tdv2b3c4d5e6f
Create Date: 2026-07-21 14:13:10.030668

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '56bd2bef4cf9'
down_revision = ('t9u5v1w7x3y0', 'tdv2b3c4d5e6f')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
