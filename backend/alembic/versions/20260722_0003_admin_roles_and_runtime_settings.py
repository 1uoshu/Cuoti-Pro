"""Add administrator role and persisted runtime settings.

Revision ID: 20260722_0003
Revises: 20260721_0002
Create Date: 2026-07-22 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260722_0003"
down_revision: Union[str, Sequence[str], None] = "20260721_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(length=16), server_default="student", nullable=False))
    op.add_column("users", sa.Column("admin_slot", sa.Integer(), nullable=True))
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_admin_slot", ["admin_slot"])
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    users = sa.table("users", sa.column("id", sa.Integer()), sa.column("role", sa.String()), sa.column("admin_slot", sa.Integer()))
    first_user_id = op.get_bind().execute(sa.select(users.c.id).order_by(users.c.id).limit(1)).scalar_one_or_none()
    if first_user_id is not None:
        op.execute(users.update().where(users.c.id == first_user_id).values(role="admin", admin_slot=1))


def downgrade() -> None:
    op.drop_table("system_settings")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_admin_slot", type_="unique")
    op.drop_column("users", "admin_slot")
    op.drop_column("users", "role")
