"""Add users.last_login_at for Profile account-and-security card.

Revision ID: 20260723_0005
Revises: 20260723_0004
Create Date: 2026-07-23 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0005"
down_revision: Union[str, Sequence[str], None] = "20260723_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
