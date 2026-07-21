from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.kernel.auth.dependencies import get_current_user
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.jobs import KernelBackgroundTasks
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.assignment_grading.models import Assignment, ProcessingTask, Question
from app.plugins.assignment_grading.schemas import QuestionUpdateRequest
from app.plugins.assignment_grading.serializers import serialize_assignment, serialize_question, serialize_task
from app.plugins.assignment_grading.service import create_assignment, process_assignment_task, update_and_regrade_question


router = APIRouter(tags=["assignment-grading"])


@router.post("/assignments")
async def upload_assignment(
    request: Request,
    background_tasks: KernelBackgroundTasks,
    file: UploadFile = File(...),
    subject: str = Form(...),
    title: str | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    context = get_kernel_context()
    assignment, task = await create_assignment(context, db, user, file, subject, title)
    context.capabilities.jobs.enqueue(background_tasks, process_assignment_task, task.id)
    context.capabilities.audit.record(
        db,
        event_type="assignment.uploaded",
        actor=user,
        resource_type="assignment",
        resource_id=assignment.id,
        summary="Assignment uploaded and grading task queued",
        metadata={
            "task_id": task.id,
            "subject": assignment.subject,
            "original_filename": assignment.original_filename,
            "status": assignment.status,
        },
        request=request,
        commit=True,
    )
    return ok({"assignment_id": assignment.id, "task": serialize_task(task)})


@router.get("/assignments")
def list_assignments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assignments = db.scalars(
        select(Assignment)
        .options(selectinload(Assignment.task))
        .where(Assignment.user_id == user.id)
        .order_by(Assignment.created_at.desc())
    ).all()
    return ok([serialize_assignment(assignment) for assignment in assignments])


@router.get("/assignments/{assignment_id}")
def assignment_detail(assignment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.questions), selectinload(Assignment.task))
        .where(Assignment.id == assignment_id)
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="作业不存在")
    if assignment.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="assignment.access.denied",
            actor=user,
            outcome="failure",
            resource_type="assignment",
            resource_id=assignment.id,
            summary="User attempted to access another user's assignment",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该作业")
    return ok(serialize_assignment(assignment, include_questions=True))


@router.get("/tasks/{task_id}")
def task_detail(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.scalar(
        select(ProcessingTask)
        .join(Assignment)
        .where(ProcessingTask.id == task_id)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.assignment.user_id != user.id:
        get_kernel_context().capabilities.audit.record(
            db,
            event_type="assignment.task.access.denied",
            actor=user,
            outcome="failure",
            resource_type="processing_task",
            resource_id=task.id,
            summary="User attempted to access another user's grading task",
            commit=True,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该任务")
    return ok(serialize_task(task))


@router.put("/questions/{question_id}")
async def correct_question(
    question_id: int,
    payload: QuestionUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    question = db.scalar(select(Question).options(selectinload(Question.assignment)).where(Question.id == question_id))
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    question = await update_and_regrade_question(get_kernel_context(), db, user, question, payload)
    return ok(serialize_question(question))
