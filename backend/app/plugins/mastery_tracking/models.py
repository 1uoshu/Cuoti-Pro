from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.kernel.database import Base
from app.kernel.models import TimestampMixin


class KnowledgePoint(TimestampMixin, Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("subject", "name", name="uq_knowledge_point_subject_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class MasteryRecord(TimestampMixin, Base):
    __tablename__ = "mastery_records"
    __table_args__ = (UniqueConstraint("user_id", "subject", "knowledge_point", name="uq_mastery_user_subject_point"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(128), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
