from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class WrongQuestion(TimestampMixin, Base):
    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    knowledge_point: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    wrong_reason: Mapped[Optional[str]] = mapped_column(Text)
    wrong_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="unreviewed", nullable=False)
    question: Mapped["Question"] = relationship(back_populates="wrong_question")
