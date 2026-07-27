from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.wrong_question_book.service import (
    get_wrong_question_detail,
    list_wrong_questions,
    save_question_feedback,
    update_wrong_question_status,
)

router = APIRouter(tags=["wrong-question-book"])


# ── 列表 ──────────────────────────────────────────

@router.get("/wrong-questions")
def wrong_questions(subject: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_wrong_questions(db, user.id, subject))


# ── 详情 ──────────────────────────────────────────

@router.get("/wrong-questions/{wrong_question_id}")
def wrong_question_detail(
    wrong_question_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_wrong_question_detail(db, wrong_question_id, user.id)
    # 审计
    context = request.app.state.kernel_context
    context.capabilities.audit.record(
        db,
        event_type="wrong_question.viewed",
        actor_user_id=user.id,
        resource_type="wrong_question",
        resource_id=wrong_question_id,
        summary="Student viewed wrong question detail",
    )
    db.commit()
    return ok(result)


# ── 状态流转 ──────────────────────────────────────

class StatusPatch(BaseModel):
    status: str = Field(..., pattern=r"^(active|reviewed|archived)$")


@router.patch("/wrong-questions/{wrong_question_id}/status")
def wrong_question_status(
    wrong_question_id: int,
    body: StatusPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = update_wrong_question_status(db, wrong_question_id, user.id, body.status)
    # 审计
    context = request.app.state.kernel_context
    context.capabilities.audit.record(
        db,
        event_type="wrong_question.status_changed",
        actor_user_id=user.id,
        resource_type="wrong_question",
        resource_id=wrong_question_id,
        summary=f"Wrong question status changed to {body.status}",
        metadata={"new_status": body.status},
    )
    db.commit()
    return ok({
        "id": item.id,
        "status": item.status,
        "wrong_count": item.wrong_count,
    })


# ── 好差评 ────────────────────────────────────────

class FeedbackRequest(BaseModel):
    rating: str = Field(..., pattern=r"^(good|bad)$")
    comment: str | None = Field(None, max_length=500)


@router.post("/questions/{question_id}/feedback")
def question_feedback(
    question_id: int,
    body: FeedbackRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    save_question_feedback(db, user.id, question_id, body.rating, body.comment)
    # 审计
    context = request.app.state.kernel_context
    context.capabilities.audit.record(
        db,
        event_type="question.feedback",
        actor_user_id=user.id,
        resource_type="question",
        resource_id=question_id,
        summary=f"Student gave {body.rating} feedback",
        metadata={"rating": body.rating},
    )
    db.commit()
    return ok({"recorded": True})
