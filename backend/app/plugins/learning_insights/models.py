from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


DIFFICULTY_CHOICES = ("adaptive", "basic", "variation", "advanced")


class UserPreferences(TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_preferences_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    daily_goal: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    review_time: Mapped[str] = mapped_column(String(5), default="19:30", nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="adaptive", nullable=False)
    weak_reminder: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


DEFAULT_PREFERENCES = {
    "daily_goal": 20,
    "review_time": "19:30",
    "difficulty": "adaptive",
    "weak_reminder": True,
}


def serialize_preferences(record: Optional[UserPreferences]) -> dict:
    if record is None:
        return dict(DEFAULT_PREFERENCES)
    return {
        "daily_goal": record.daily_goal,
        "review_time": record.review_time,
        "difficulty": record.difficulty,
        "weak_reminder": record.weak_reminder,
    }
