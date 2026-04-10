"""add primal and team workspace fields to user

Revision ID: a4e6b2d8c1f9
Revises: f2c4e8d91ab7
Create Date: 2026-03-14 21:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a4e6b2d8c1f9"
down_revision = "f2c4e8d91ab7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "old_team_id",
            existing_type=sa.Integer(),
            nullable=True,
            new_column_name="primals_team_id",
        )
        batch_op.alter_column(
            "old_role_id",
            existing_type=sa.Integer(),
            nullable=True,
            new_column_name="primals_role_id",
        )
        batch_op.add_column(sa.Column("team_workspace_team_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("team_workspace_role_id", sa.Integer(), nullable=True))

    op.execute('UPDATE "user" SET primals_team_id = team_id WHERE primals_team_id IS NULL')
    op.execute('UPDATE "user" SET primals_role_id = user_role_id WHERE primals_role_id IS NULL')


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("team_workspace_role_id")
        batch_op.drop_column("team_workspace_team_id")
        batch_op.alter_column(
            "primals_role_id",
            existing_type=sa.Integer(),
            nullable=True,
            new_column_name="old_role_id",
        )
        batch_op.alter_column(
            "primals_team_id",
            existing_type=sa.Integer(),
            nullable=True,
            new_column_name="old_team_id",
        )
