"""unique_route_plan_client_id_per_team

Revision ID: 79738f41626f
Revises: a7d3f2c1b9e6
Create Date: 2026-03-27 22:48:24.597170

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '79738f41626f'
down_revision = 'a7d3f2c1b9e6'
branch_labels = None
depends_on = None


def upgrade():
    # Nullify client_id on duplicate rows, keeping the earliest per (team_id, client_id).
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE route_plan
        SET client_id = NULL
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM route_plan
            WHERE client_id IS NOT NULL
            GROUP BY team_id, client_id
        )
        AND client_id IS NOT NULL
    """))

    with op.batch_alter_table('route_plan', schema=None) as batch_op:
        batch_op.create_index(
            'uq_route_plan_team_client_id',
            ['team_id', 'client_id'],
            unique=True,
            postgresql_where=sa.text('client_id IS NOT NULL'),
        )


def downgrade():
    with op.batch_alter_table('route_plan', schema=None) as batch_op:
        batch_op.drop_index('uq_route_plan_team_client_id')
