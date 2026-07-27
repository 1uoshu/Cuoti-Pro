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


def get_wrong_question_detail(db: Session, question_id: int, user_id: int) -> dict | None:
    """获取错题详情（带权限检查）。
    返回包含原题快照+学生答案+标答+错因的完整字典。
    如果 question 不属于该 user_id，返回 None（调用方处理 404）。
    """
    wq = db.scalar(
        select(WrongQuestion)
        .options(selectinload(WrongQuestion.question).selectinload(Question.assignment))
        .where(WrongQuestion.question_id == question_id)
    )
    if wq is None or wq.user_id != user_id:
        return None
    q = wq.question
    return {
        "wrong_question_id": wq.id,
        "subject": wq.subject,
        "knowledge_point": wq.knowledge_point,
        "wrong_reason": wq.wrong_reason,
        "wrong_count": wq.wrong_count,
        "status": wq.status,
        "created_at": wq.created_at.isoformat() if wq.created_at else None,
        "question": serialize_question(q),
    }


def update_wrong_question_status(db: Session, question_id: int, user_id: int, new_status: str) -> dict | None:
    """更新错题状态。允许的状态：unreviewed, reviewing, mastered, archived。
    带权限检查。返回更新后的字典，不存在返回 None。
    """
    allowed = {"unreviewed", "reviewing", "mastered", "archived"}
    if new_status not in allowed:
        raise ValueError(f"无效状态：{new_status}，允许：{', '.join(sorted(allowed))}")
    wq = db.scalar(
        select(WrongQuestion)
        .where(WrongQuestion.question_id == question_id, WrongQuestion.user_id == user_id)
    )
    if wq is None:
        return None
    wq.status = new_status
    db.commit()
    db.refresh(wq)
    return {"id": wq.id, "status": wq.status, "question_id": question_id}


def confirm_review(db: Session, question_id: int, user_id: int) -> dict | None:
    """待复核确认：学生确认后，将 needs_review=False 的题归档到错题本。
    如果该题已归档，返回已归档记录。
    如果该题 confidence 不足，仍归档但标记 status="reviewing"。
    """
    question = db.get(Question, question_id)
    if question is None:
        return None
    # 检查该题是否属于该学生的作业
    assignment = question.assignment
    if assignment is None or assignment.user_id != user_id:
        return None
    # 归档到错题本
    wq = db.scalar(select(WrongQuestion).where(WrongQuestion.question_id == question_id))
    if wq is not None:
        return {"id": wq.id, "status": wq.status, "already_archived": True}
    wq = WrongQuestion(
        user_id=user_id,
        question_id=question_id,
        subject=assignment.subject,
        knowledge_point=question.knowledge_point,
        wrong_reason=question.explanation,
        status="reviewing" if question.needs_review else "unreviewed",
    )
    db.add(wq)
    question.needs_review = False  # 确认后不再标记待复核
    db.commit()
    db.refresh(wq)
    return {"id": wq.id, "status": wq.status, "already_archived": False}
