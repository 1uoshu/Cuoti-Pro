from sqlalchemy import select
from sqlalchemy.orm import Session

from app.plugins.mastery_tracking.models import KnowledgePoint, MasteryRecord


def ensure_knowledge_point(db: Session, subject: str, name: str | None) -> None:
    if not name:
        return
    normalized_name = name.strip()
    if not normalized_name:
        return
    point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.subject == subject, KnowledgePoint.name == normalized_name))
    if point is None:
        db.add(KnowledgePoint(subject=subject, name=normalized_name))


def update_mastery(
    db: Session, user_id: int, subject: str, knowledge_point: str | None, is_correct: bool, delta: int = 1
) -> None:
    if not knowledge_point:
        return
    record = db.scalar(
        select(MasteryRecord).where(
            MasteryRecord.user_id == user_id,
            MasteryRecord.subject == subject,
            MasteryRecord.knowledge_point == knowledge_point,
        )
    )
    if record is None:
        if delta < 0:
            return
        record = MasteryRecord(
            user_id=user_id,
            subject=subject,
            knowledge_point=knowledge_point,
            correct_count=0,
            wrong_count=0,
            mastery_score=0,
        )
        db.add(record)
    if is_correct:
        record.correct_count = max(0, record.correct_count + delta)
    else:
        record.wrong_count = max(0, record.wrong_count + delta)
    total = record.correct_count + record.wrong_count
    record.mastery_score = round(record.correct_count / total * 100, 1) if total else 0


def serialize_mastery(record: MasteryRecord) -> dict:
    return {
        "id": record.id,
        "subject": record.subject,
        "knowledge_point": record.knowledge_point,
        "mastery_score": record.mastery_score,
        "correct_count": record.correct_count,
        "wrong_count": record.wrong_count,
    }
