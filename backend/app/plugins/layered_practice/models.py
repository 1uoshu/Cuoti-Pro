from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class PracticeTask(TimestampMixin, Base):
    __tablename__ = "practice_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(128), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="ready", nullable=False)
    student_score: Mapped[Optional[float]] = mapped_column(Float)
    questions: Mapped[list["PracticeQuestion"]] = relationship(
        back_populates="practice_task", cascade="all, delete-orphan"
    )


class PracticeQuestion(TimestampMixin, Base):
    __tablename__ = "practice_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_task_id: Mapped[int] = mapped_column(ForeignKey("practice_tasks.id"), index=True, nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    standard_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_warning: Mapped[Optional[str]] = mapped_column(String(255))
    practice_task: Mapped["PracticeTask"] = relationship(back_populates="questions")
    answers: Mapped[list["PracticeAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class PracticeAnswer(TimestampMixin, Base):
    __tablename__ = "practice_answers"
    __table_args__ = (UniqueConstraint("practice_question_id", name="uq_practice_answer_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_question_id: Mapped[int] = mapped_column(ForeignKey("practice_questions.id"), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_warning: Mapped[Optional[str]] = mapped_column(String(255))
    question: Mapped["PracticeQuestion"] = relationship(back_populates="answers")
