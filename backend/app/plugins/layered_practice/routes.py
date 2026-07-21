from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.kernel.auth.dependencies import get_current_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.layered_practice.models import PracticeQuestion, PracticeTask
from app.plugins.layered_practice.schemas import PracticeCreateRequest, PracticeSubmitRequest
from app.plugins.layered_practice.serializers import serialize_practice
from app.plugins.layered_practice.service import create_practice_task, submit_practice_answers


router = APIRouter(tags=["layered-practice"])


@router.post("/practices")
async def create_practice(
    payload: PracticeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = await create_practice_task(get_kernel_context(), db, user, payload)
    return ok(serialize_practice(task))


@router.get("/practices/{practice_id}")
def practice_detail(practice_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.scalar(
        select(PracticeTask)
        .options(selectinload(PracticeTask.questions).selectinload(PracticeQuestion.answers))
        .where(PracticeTask.id == practice_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if task.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="practice.access.denied",
            actor=user,
            outcome="failure",
            resource_type="practice_task",
            resource_id=task.id,
            summary="User attempted to access another user's practice task",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该练习")
    return ok(serialize_practice(task))


@router.post("/practices/{practice_id}/submit")
async def submit_practice(
    practice_id: int,
    payload: PracticeSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(
        select(PracticeTask)
        .options(selectinload(PracticeTask.questions).selectinload(PracticeQuestion.answers))
        .where(PracticeTask.id == practice_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="练习不存在")
    if task.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="practice.submit.denied",
            actor=user,
            outcome="failure",
            resource_type="practice_task",
            resource_id=task.id,
            summary="User attempted to submit another user's practice task",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权提交该练习")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="该练习已经提交")
    task = await submit_practice_answers(get_kernel_context(), db, user, task, payload)
    db.refresh(task)
    task = db.scalar(
        select(PracticeTask)
        .options(selectinload(PracticeTask.questions).selectinload(PracticeQuestion.answers))
        .where(PracticeTask.id == task.id)
    )
    return ok(serialize_practice(task))
