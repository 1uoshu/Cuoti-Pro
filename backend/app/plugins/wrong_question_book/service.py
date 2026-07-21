from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.plugins.assignment_grading.models import Question
from app.plugins.assignment_grading.serializers import serialize_question
from app.plugins.wrong_question_book.models import WrongQuestion


def upsert_wrong_question(
    db: Session,
    *,
    user_id: int,
    question_id: int,
    subject: str,
    knowledge_point: str | None,
    wrong_reason: str | None,
) -> None:
    wrong_question = db.scalar(select(WrongQuestion).where(WrongQuestion.question_id == question_id))
    if wrong_question is None:
        db.add(
            WrongQuestion(
                user_id=user_id,
                question_id=question_id,
                subject=subject,
                knowledge_point=knowledge_point,
                wrong_reason=wrong_reason,
            )
        )
        return
    wrong_question.subject = subject
    wrong_question.knowledge_point = knowledge_point
    wrong_question.wrong_reason = wrong_reason


def remove_wrong_question(db: Session, question_id: int) -> None:
    wrong_question = db.scalar(select(WrongQuestion).where(WrongQuestion.question_id == question_id))
    if wrong_question is not None:
        db.delete(wrong_question)


def list_wrong_questions(db: Session, user_id: int, subject: str | None = None) -> list[dict]:
    query = (
        select(WrongQuestion)
        .options(selectinload(WrongQuestion.question))
        .where(WrongQuestion.user_id == user_id)
        .order_by(WrongQuestion.updated_at.desc())
    )
    if subject:
        query = query.where(WrongQuestion.subject == subject)
    items = db.scalars(query).all()
    return [
        {
            "id": item.id,
            "subject": item.subject,
            "knowledge_point": item.knowledge_point,
            "wrong_reason": item.wrong_reason,
            "wrong_count": item.wrong_count,
            "status": item.status,
            "question": serialize_question(item.question),
        }
        for item in items
    ]


def get_recent_mistakes(db: Session, user_id: int, subject: str, knowledge_point: str) -> list[str]:
    questions = db.scalars(
        select(Question)
        .join(WrongQuestion)
        .where(
            WrongQuestion.user_id == user_id,
            WrongQuestion.subject == subject,
            WrongQuestion.knowledge_point == knowledge_point,
        )
        .order_by(WrongQuestion.updated_at.desc())
        .limit(5)
    ).all()
    return [question.content for question in questions]
