from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.plugins.assignment_grading.models import Question
from app.plugins.assignment_grading.serializers import serialize_question
from app.plugins.wrong_question_book.feedback_models import QuestionFeedback
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
            "created_at": str(item.created_at) if item.created_at else None,
            "question": serialize_question(item.question),
        }
        for item in items
    ]


def get_wrong_question_detail(db: Session, wrong_question_id: int, user_id: int) -> dict:
    """错题详情：完整 question 对象。"""
    item = db.get(WrongQuestion, wrong_question_id)
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="错题不存在")
    if item.user_id != user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="无权访问该错题")

    question = item.question
    return {
        "id": item.id,
        "subject": item.subject,
        "knowledge_point": item.knowledge_point,
        "wrong_reason": item.wrong_reason,
        "wrong_count": item.wrong_count,
        "status": item.status,
        "created_at": str(item.created_at) if item.created_at else None,
        "question": {
            "id": question.id,
            "question_number": question.question_number,
            "content": question.content,
            "student_answer": question.student_answer,
            "correct_answer": question.correct_answer,
            "score": question.score,
            "max_score": question.max_score,
            "is_correct": question.is_correct,
            "explanation": question.explanation,
            "confidence": question.confidence,
            "needs_review": question.needs_review,
        } if question else None,
    }


def update_wrong_question_status(db: Session, wrong_question_id: int, user_id: int, new_status: str) -> WrongQuestion:
    """错题状态流转：active ↔ reviewed → archived。"""
    from fastapi import HTTPException

    item = db.get(WrongQuestion, wrong_question_id)
    if item is None:
        raise HTTPException(status_code=404, detail="错题不存在")
    if item.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权修改该错题")

    valid_transitions = {
        "active": {"reviewed", "archived"},
        "reviewed": {"active", "archived"},
        "archived": set(),  # 不可逆转
    }
    current = item.status
    allowed = valid_transitions.get(current, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不允许从 {current} 转为 {new_status}，合法目标：{', '.join(allowed) or '无'}",
        )

    item.status = new_status
    db.commit()
    db.refresh(item)
    return item


def save_question_feedback(db: Session, user_id: int, question_id: int, rating: str, comment: str | None) -> None:
    """保存学生对题目的好/差评。"""
    from fastapi import HTTPException

    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 校验题目属于当前用户（通过 assignment → user_id）
    from app.plugins.assignment_grading.models import Assignment
    assignment = db.get(Assignment, question.assignment_id)
    if assignment is None or assignment.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权评价该题目")

    existing = db.scalar(
        select(QuestionFeedback).where(
            QuestionFeedback.user_id == user_id,
            QuestionFeedback.question_id == question_id,
        )
    )
    if existing:
        existing.rating = rating
        existing.comment = comment
    else:
        db.add(QuestionFeedback(
            user_id=user_id,
            question_id=question_id,
            rating=rating,
            comment=comment,
        ))
    db.commit()


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
