import re

from pydantic import BaseModel, Field, field_validator

from app.plugins.learning_insights.models import DIFFICULTY_CHOICES


_REVIEW_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ProfilePreferencesUpdate(BaseModel):
    daily_goal: int | None = Field(default=None, ge=5, le=100)
    review_time: str | None = None
    difficulty: str | None = None
    weak_reminder: bool | None = None

    @field_validator("daily_goal")
    @classmethod
    def validate_daily_goal_step(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value % 5 != 0:
            raise ValueError("每日目标题数必须是 5 的倍数")
        return value

    @field_validator("review_time")
    @classmethod
    def validate_review_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _REVIEW_TIME_RE.match(value):
            raise ValueError("复习提醒时间格式必须为 HH:mm")
        return value

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in DIFFICULTY_CHOICES:
            raise ValueError("难度策略必须是 adaptive / basic / variation / advanced 之一")
        return value
