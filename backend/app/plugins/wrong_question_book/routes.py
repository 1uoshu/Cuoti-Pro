from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.wrong_question_book.service import (
    confirm_review,
    get_wrong_question_detail,
    list_wrong_questions,
    update_wrong_question_status,
)


router = APIRouter(tags=["wrong-question-book"])


# ── 列表 ──────────────────────────────────────────

@router.get("/wrong-questions")
def wrong_questions(subject: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_wrong_questions(db, user.id, subject))


@router.get("/wrong-questions/{question_id}")
def wrong_question_detail(
    question_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """错题详情（查看进审计）"""
    detail = get_wrong_question_detail(db, question_id, user.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="错题不存在")
    context = get_kernel_context()
    context.capabilities.audit.record(
        db, event_type="wrong_question.viewed", actor=user,
        resource_type="wrong_question", resource_id=question_id,
        summary="学生查看错题详情", request=request, commit=True,
    )
    return ok(detail)


@router.patch("/wrong-questions/{question_id}/status")
def update_wrong_question_status_route(
    question_id: int,
    status: str = Form(...),
    request: Request = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新错题状态"""
    try:
        result = update_wrong_question_status(db, question_id, user.id, status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="错题不存在")
    context = get_kernel_context()
    context.capabilities.audit.record(
        db, event_type="wrong_question.status_changed", actor=user,
        resource_type="wrong_question", resource_id=question_id,
        summary=f"错题状态变更为 {status}", metadata={"new_status": status},
        request=request, commit=True,
    )
    return ok(result)


@router.post("/questions/{question_id}/confirm-review")
def confirm_review_route(
    question_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """待复核确认：学生确认后归档到错题本"""
    result = confirm_review(db, question_id, user.id)
    if result is None:
        raise HTTPException(status_code=404, detail="题目不存在或无权限")
    context = get_kernel_context()
    context.capabilities.audit.record(
        db, event_type="wrong_question.review_confirmed", actor=user,
        resource_type="question", resource_id=question_id,
        summary="学生确认待复核题目", request=request, commit=True,
    )
    return ok(result)
