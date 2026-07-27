"""Add question_feedback table for student feedback on grading.

Revision ID: 20260727_0008
Revises: 20260727_0007
Create Date: 2026-07-27 00:00:08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260727_0008"
down_revision: Union[str, Sequence[str], None] = "20260727_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "question_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("rating", sa.String(length=8), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_question_feedback_user_id", "question_feedback", ["user_id"])
    op.create_index("ix_question_feedback_question_id", "question_feedback", ["question_id"])
    op.create_unique_constraint("uq_question_feedback_user_question", "question_feedback", ["user_id", "question_id"])


def downgrade() -> None:
    op.drop_constraint("uq_question_feedback_user_question", "question_feedback", type_="unique")
    op.drop_index("ix_question_feedback_question_id", table_name="question_feedback")
    op.drop_index("ix_question_feedback_user_id", table_name="question_feedback")
    op.drop_table("question_feedback")
