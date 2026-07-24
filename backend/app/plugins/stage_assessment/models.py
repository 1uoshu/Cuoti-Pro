from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class ExamTask(TimestampMixin, Base):
    __tablename__ = "exam_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    exam_type: Mapped[str] = mapped_column(String(24), nullable=False)
    knowledge_points: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="generating", index=True, nullable=False)
    student_score: Mapped[Optional[float]] = mapped_column(Float)
    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam_task",
        cascade="all, delete-orphan",
        order_by="ExamQuestion.question_number",
    )


class ExamQuestion(TimestampMixin, Base):
    __tablename__ = "exam_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_task_id: Mapped[int] = mapped_column(ForeignKey("exam_tasks.id"), index=True, nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    standard_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_warning: Mapped[Optional[str]] = mapped_column(String(255))
    exam_task: Mapped[ExamTask] = relationship(back_populates="questions")
    answers: Mapped[list["ExamAnswer"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="ExamAnswer.id",
    )


class ExamAnswer(TimestampMixin, Base):
    __tablename__ = "exam_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_question_id: Mapped[int] = mapped_column(
        ForeignKey("exam_questions.id"),
        unique=True,
        nullable=False,
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_warning: Mapped[Optional[str]] = mapped_column(String(255))
    question: Mapped[ExamQuestion] = relationship(back_populates="answers")
