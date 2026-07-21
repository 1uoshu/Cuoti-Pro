"""Persist practice generation and grading confidence.

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260721_0002"
down_revision: Union[str, Sequence[str], None] = "20260721_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("practice_questions", sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column("practice_questions", sa.Column("confidence_warning", sa.String(length=255)))
    op.add_column("practice_answers", sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column("practice_answers", sa.Column("confidence_warning", sa.String(length=255)))


def downgrade() -> None:
    op.drop_column("practice_answers", "confidence_warning")
    op.drop_column("practice_answers", "confidence")
    op.drop_column("practice_questions", "confidence_warning")
    op.drop_column("practice_questions", "confidence")

