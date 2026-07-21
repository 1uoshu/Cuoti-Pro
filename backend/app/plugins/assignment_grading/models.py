from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True, nullable=False)
    total_score: Mapped[Optional[float]] = mapped_column(Float)
    student_score: Mapped[Optional[float]] = mapped_column(Float)
    overall_comment: Mapped[Optional[str]] = mapped_column(Text)
    weak_points: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    user: Mapped["User"] = relationship()
    questions: Mapped[list["Question"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    task: Mapped[Optional["ProcessingTask"]] = relationship(back_populates="assignment", uselist=False)


class ProcessingTask(TimestampMixin, Base):
    __tablename__ = "processing_tasks"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True, nullable=False)
    step: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    assignment: Mapped["Assignment"] = relationship(back_populates="task")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True, nullable=False)
    question_number: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    student_answer: Mapped[Optional[str]] = mapped_column(Text)
    correct_answer: Mapped[Optional[str]] = mapped_column(Text)
    question_type: Mapped[Optional[str]] = mapped_column(String(32))
    knowledge_point: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    score: Mapped[Optional[float]] = mapped_column(Float)
    max_score: Mapped[Optional[float]] = mapped_column(Float)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assignment: Mapped["Assignment"] = relationship(back_populates="questions")
    wrong_question: Mapped[Optional["WrongQuestion"]] = relationship(back_populates="question", uselist=False)
