"""add default_city_key to team

Revision ID: h2f1c9a8d4e7
Revises: y4z0b6c2d8e4
Create Date: 2026-03-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h2f1c9a8d4e7'
down_revision = 'y4z0b6c2d8e4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('team', schema=None) as batch_op:
        batch_op.add_column(sa.Column('default_city_key', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('team', schema=None) as batch_op:
        batch_op.drop_column('default_city_key')
