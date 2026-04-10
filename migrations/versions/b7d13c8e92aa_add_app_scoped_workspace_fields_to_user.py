"""add app scoped workspace fields to user

Revision ID: b7d13c8e92aa
Revises: a4e6b2d8c1f9
Create Date: 2026-03-14 23:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b7d13c8e92aa"
down_revision = "a4e6b2d8c1f9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("admin_app_current_workspace", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("driver_app_current_workspace", sa.String(), nullable=True))

    op.execute('UPDATE "user" SET admin_app_current_workspace = \'personal\' WHERE admin_app_current_workspace IS NULL')
    op.execute(
        """
        UPDATE "user"
        SET driver_app_current_workspace = CASE
            WHEN team_workspace_team_id IS NOT NULL AND team_workspace_role_id IS NOT NULL THEN 'personal'
            WHEN primals_team_id IS NOT NULL
             AND primals_role_id IS NOT NULL
             AND (team_id != primals_team_id OR user_role_id != primals_role_id) THEN 'team'
            ELSE 'personal'
        END
        WHERE driver_app_current_workspace IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("driver_app_current_workspace")
        batch_op.drop_column("admin_app_current_workspace")
