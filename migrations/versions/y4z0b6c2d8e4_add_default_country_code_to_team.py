"""add default_country_code to team

Revision ID: y4z0b6c2d8e4
Revises: 7f66a23de2a6
Create Date: 2026-03-21 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y4z0b6c2d8e4'
down_revision = '7f66a23de2a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('team', schema=None) as batch_op:
        batch_op.add_column(sa.Column('default_country_code', sa.String(length=2), nullable=True))


def downgrade():
    with op.batch_alter_table('team', schema=None) as batch_op:
        batch_op.drop_column('default_country_code')