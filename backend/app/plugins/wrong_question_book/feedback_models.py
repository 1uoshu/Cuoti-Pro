from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class QuestionFeedback(TimestampMixin, Base):
    """Per-question feedback from students (good/bad rating)."""
    __tablename__ = "question_feedback"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_question_feedback_user_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True, nullable=False)
    rating: Mapped[str] = mapped_column(String(8), nullable=False)  # "good" or "bad"
    comment: Mapped[Optional[str]] = mapped_column(Text)
