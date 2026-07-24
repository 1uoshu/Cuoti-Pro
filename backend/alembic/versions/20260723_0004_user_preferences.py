"""Add user profile preferences for learning insights.

Revision ID: 20260723_0004
Revises: 20260722_0003
Create Date: 2026-07-23 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0004"
down_revision: Union[str, Sequence[str], None] = "20260722_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("daily_goal", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("review_time", sa.String(length=5), nullable=False, server_default="19:30"),
        sa.Column("difficulty", sa.String(length=16), nullable=False, server_default="adaptive"),
        sa.Column("weak_reminder", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user"),
    )
    op.create_index("ix_user_preferences_user_id", "user_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
