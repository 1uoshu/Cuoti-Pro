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
