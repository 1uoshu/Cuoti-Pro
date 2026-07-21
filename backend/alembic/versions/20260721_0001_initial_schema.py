"""Initial smart learning schema.

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260721_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=False),
        sa.Column("grade", sa.String(length=32)),
        sa.Column("school", sa.String(length=128)),
        sa.Column("main_subject", sa.String(length=32)),
        *timestamp_columns(),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("actor_username", sa.String(length=32)),
        sa.Column("resource_type", sa.String(length=64)),
        sa.Column("resource_id", sa.String(length=64)),
        sa.Column("summary", sa.String(length=255)),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=255)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text()),
        *timestamp_columns(),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_outcome", "audit_logs", ["outcome"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_actor_username", "audit_logs", ["actor_username"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("total_score", sa.Float()),
        sa.Column("student_score", sa.Float()),
        sa.Column("overall_comment", sa.Text()),
        sa.Column("weak_points", sa.JSON(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_assignments_user_id", "assignments", ["user_id"])
    op.create_index("ix_assignments_subject", "assignments", ["subject"])
    op.create_index("ix_assignments_status", "assignments", ["status"])

    op.create_table(
        "processing_tasks",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text()),
        *timestamp_columns(),
    )
    op.create_index("ix_processing_tasks_status", "processing_tasks", ["status"])

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text()),
        *timestamp_columns(),
        sa.UniqueConstraint("subject", "name", name="uq_knowledge_point_subject_name"),
    )
    op.create_index("ix_knowledge_points_subject", "knowledge_points", ["subject"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id"), nullable=False),
        sa.Column("question_number", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("student_answer", sa.Text()),
        sa.Column("correct_answer", sa.Text()),
        sa.Column("question_type", sa.String(length=32)),
        sa.Column("knowledge_point", sa.String(length=128)),
        sa.Column("score", sa.Float()),
        sa.Column("max_score", sa.Float()),
        sa.Column("is_correct", sa.Boolean()),
        sa.Column("explanation", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_questions_assignment_id", "questions", ["assignment_id"])
    op.create_index("ix_questions_knowledge_point", "questions", ["knowledge_point"])

    op.create_table(
        "wrong_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False, unique=True),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("knowledge_point", sa.String(length=128)),
        sa.Column("wrong_reason", sa.Text()),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_wrong_questions_user_id", "wrong_questions", ["user_id"])
    op.create_index("ix_wrong_questions_subject", "wrong_questions", ["subject"])
    op.create_index("ix_wrong_questions_knowledge_point", "wrong_questions", ["knowledge_point"])

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("knowledge_point", sa.String(length=128), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("student_score", sa.Float()),
        *timestamp_columns(),
    )
    op.create_index("ix_practice_tasks_user_id", "practice_tasks", ["user_id"])

    op.create_table(
        "practice_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_task_id", sa.Integer(), sa.ForeignKey("practice_tasks.id"), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("standard_answer", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        *timestamp_columns(),
    )
    op.create_index("ix_practice_questions_practice_task_id", "practice_questions", ["practice_task_id"])

    op.create_table(
        "practice_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("practice_question_id", sa.Integer(), sa.ForeignKey("practice_questions.id"), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("practice_question_id", name="uq_practice_answer_question"),
    )

    op.create_table(
        "mastery_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("knowledge_point", sa.String(length=128), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.UniqueConstraint("user_id", "subject", "knowledge_point", name="uq_mastery_user_subject_point"),
    )
    op.create_index("ix_mastery_records_user_id", "mastery_records", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mastery_records_user_id", table_name="mastery_records")
    op.drop_table("mastery_records")
    op.drop_table("practice_answers")
    op.drop_index("ix_practice_questions_practice_task_id", table_name="practice_questions")
    op.drop_table("practice_questions")
    op.drop_index("ix_practice_tasks_user_id", table_name="practice_tasks")
    op.drop_table("practice_tasks")
    op.drop_index("ix_wrong_questions_knowledge_point", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_subject", table_name="wrong_questions")
    op.drop_index("ix_wrong_questions_user_id", table_name="wrong_questions")
    op.drop_table("wrong_questions")
    op.drop_index("ix_questions_knowledge_point", table_name="questions")
    op.drop_index("ix_questions_assignment_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_knowledge_points_subject", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_index("ix_processing_tasks_status", table_name="processing_tasks")
    op.drop_table("processing_tasks")
    op.drop_index("ix_assignments_status", table_name="assignments")
    op.drop_index("ix_assignments_subject", table_name="assignments")
    op.drop_index("ix_assignments_user_id", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_username", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_outcome", table_name="audit_logs")
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
