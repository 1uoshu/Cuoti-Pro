from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.kernel.auth.dependencies import get_current_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.layered_practice.schemas import PracticeSubmitRequest
from app.plugins.stage_assessment.models import ExamQuestion, ExamTask
from app.plugins.stage_assessment.schemas import ExamCreateRequest
from app.plugins.stage_assessment.serializers import serialize_exam
from app.plugins.stage_assessment.service import create_exam_task, get_score_compare, submit_exam_answers


router = APIRouter(tags=["stage-assessment"])


@router.post("/exams")
async def create_exam(
    payload: ExamCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = await create_exam_task(get_kernel_context(), db, user, payload)
    return ok(serialize_exam(task))


@router.get("/exams")
def list_exams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.scalars(
        select(ExamTask)
        .where(ExamTask.user_id == user.id)
        .order_by(ExamTask.created_at.desc(), ExamTask.id.desc())
    ).all()
    return ok([serialize_exam(task) for task in tasks])


@router.get("/exams/score-compare")
def score_compare(
    subject: str | None = Query(default=None, min_length=1, max_length=32),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    normalized_subject = subject.strip() if subject else None
    return ok(get_score_compare(db, user.id, normalized_subject))


@router.get("/exams/{exam_id}")
def exam_detail(exam_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.scalar(
        select(ExamTask)
        .options(selectinload(ExamTask.questions).selectinload(ExamQuestion.answers))
        .where(ExamTask.id == exam_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="考核不存在")
    if task.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="exam.access.denied",
            actor=user,
            outcome="failure",
            resource_type="exam_task",
            resource_id=task.id,
            summary="User attempted to access another user's exam",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该考核")
    return ok(serialize_exam(task, include_questions=True))


@router.post("/exams/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    payload: PracticeSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = db.scalar(
        select(ExamTask)
        .options(selectinload(ExamTask.questions).selectinload(ExamQuestion.answers))
        .where(ExamTask.id == exam_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="考核不存在")
    if task.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="exam.submit.denied",
            actor=user,
            outcome="failure",
            resource_type="exam_task",
            resource_id=task.id,
            summary="User attempted to submit another user's exam",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权提交该考核")
    if task.status == "completed":
        raise HTTPException(status_code=409, detail="该考核已经提交")
    if task.status == "submitting":
        raise HTTPException(status_code=409, detail="该考核正在提交")
    if task.status != "ready":
        raise HTTPException(status_code=409, detail="该考核当前不可提交")

    claim = db.execute(
        update(ExamTask)
        .where(ExamTask.id == exam_id, ExamTask.user_id == user.id, ExamTask.status == "ready")
        .values(status="submitting")
    )
    if claim.rowcount != 1:
        db.rollback()
        current_task = db.get(ExamTask, exam_id)
        if current_task is not None and current_task.status == "completed":
            raise HTTPException(status_code=409, detail="该考核已经提交")
        raise HTTPException(status_code=409, detail="该考核正在提交")
    task.status = "submitting"
    db.commit()
    try:
        await submit_exam_answers(get_kernel_context(), db, user, task, payload)
    except Exception:
        db.rollback()
        current_task = db.get(ExamTask, exam_id)
        if current_task is not None and current_task.status == "submitting":
            current_task.status = "ready"
            db.commit()
        raise
    task = db.scalar(
        select(ExamTask)
        .options(selectinload(ExamTask.questions).selectinload(ExamQuestion.answers))
        .where(ExamTask.id == exam_id)
    )
    return ok(serialize_exam(task, include_questions=True))
