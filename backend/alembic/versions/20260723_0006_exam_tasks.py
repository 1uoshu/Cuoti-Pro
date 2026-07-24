"""Add exam_tasks / exam_questions / exam_answers tables for stage_assessment.

Revision ID: 20260723_0006
Revises: 20260723_0005
Create Date: 2026-07-23 00:00:02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0006"
down_revision: Union[str, Sequence[str], None] = "20260723_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exam_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("exam_type", sa.String(length=24), nullable=False),
        sa.Column("knowledge_points", sa.JSON(), nullable=False),
        sa.Column("difficulty", sa.String(length=24), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="generating"),
        sa.Column("student_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_exam_tasks_user_id", "exam_tasks", ["user_id"])
    op.create_index("ix_exam_tasks_subject", "exam_tasks", ["subject"])
    op.create_index("ix_exam_tasks_status", "exam_tasks", ["status"])

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_task_id", sa.Integer(), sa.ForeignKey("exam_tasks.id"), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("knowledge_point", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_warning", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_exam_questions_exam_task_id", "exam_questions", ["exam_task_id"])
    op.create_index("ix_exam_questions_knowledge_point", "exam_questions", ["knowledge_point"])

    op.create_table(
        "exam_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_question_id", sa.Integer(), sa.ForeignKey("exam_questions.id"), nullable=False, unique=True),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_warning", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("exam_answers")
    op.drop_index("ix_exam_questions_knowledge_point", table_name="exam_questions")
    op.drop_index("ix_exam_questions_exam_task_id", table_name="exam_questions")
    op.drop_table("exam_questions")
    op.drop_index("ix_exam_tasks_status", table_name="exam_tasks")
    op.drop_index("ix_exam_tasks_subject", table_name="exam_tasks")
    op.drop_index("ix_exam_tasks_user_id", table_name="exam_tasks")
    op.drop_table("exam_tasks")
