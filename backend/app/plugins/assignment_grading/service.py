import asyncio
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.context import KernelContext, get_kernel_context
from app.kernel.models import User
from app.kernel.responses import SAFE_AGENT_ERROR_MESSAGE
from app.plugins.assignment_grading.models import Assignment, ProcessingTask, Question
from app.plugins.assignment_grading.schemas import ModelGradePayload, QuestionUpdateRequest
from app.plugins.assignment_grading.workflow import regrade_text_question, run_grading_workflow
from app.plugins.mastery_tracking.service import ensure_knowledge_point, update_mastery
from app.plugins.wrong_question_book.service import remove_wrong_question, upsert_wrong_question


class NoQuestionsDetected(Exception):
    pass


async def create_assignment(
    context: KernelContext,
    db: Session,
    user: User,
    file: UploadFile,
    subject: str,
    title: str | None,
) -> tuple[Assignment, ProcessingTask]:
    subject = subject.strip()
    if not subject:
        raise HTTPException(status_code=400, detail="请填写学科")
    if len(subject) > 32:
        raise HTTPException(status_code=400, detail="学科名称不能超过 32 个字符")
    # 文件大小检查（提前拦截，给出人话提示）
    content = await file.read()
    if len(content) > context.settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"文件太大，最大支持 {context.settings.max_upload_mb}MB",
        )
    await file.seek(0)  # 重置文件指针，供后续存储使用
    file_path, suffix = await context.capabilities.storage.save_upload(file, user.id, "uploads")
    assignment = Assignment(
        user_id=user.id,
        title=(title or Path(file.filename or "作业").stem)[:128],
        subject=subject,
        original_filename=file.filename or f"upload{suffix}",
        file_path=file_path,
        status="queued",
    )
    db.add(assignment)
    db.flush()
    task = ProcessingTask(id=f"task_{uuid.uuid4().hex[:24]}", assignment_id=assignment.id)
    db.add(task)
    db.commit()
    db.refresh(assignment)
    db.refresh(task)
    return assignment, task


def process_assignment_task(task_id: str) -> None:
    context = get_kernel_context()
    with context.capabilities.database.session() as db:
        try:
            task = db.get(ProcessingTask, task_id)
            if task is None or task.status == "completed":
                return
            assignment = db.get(Assignment, task.assignment_id)
            if assignment is None:
                return

            _set_task_state(task, assignment, "准备文件", 10)
            db.commit()
            _set_task_state(task, assignment, "识别并批改作业", 45)
            db.commit()

            user = db.get(User, assignment.user_id)
            if user is None:
                raise RuntimeError("assignment owner does not exist")
            payload = asyncio.run(
                run_grading_workflow(
                    context,
                    assignment.file_path,
                    assignment.subject,
                    user.grade,
                    student_id=str(user.id),
                )
            )

            if not payload.questions:
                raise NoQuestionsDetected("未能从作业中识别到题目，请上传更清晰的图片或包含实际题目的内容")

            _set_task_state(task, assignment, "保存批改结果", 85)
            db.commit()
            persist_grade_payload(context, db, assignment, payload)
            assignment.status = "completed"
            task.status = "completed"
            task.step = "completed"
            task.progress = 100
            context.capabilities.audit.record(
                db,
                event_type="assignment.grading.completed",
                actor_user_id=assignment.user_id,
                outcome="success",
                resource_type="assignment",
                resource_id=assignment.id,
                summary="Assignment grading task completed",
                metadata={"task_id": task.id, "question_count": len(payload.questions), "subject": assignment.subject},
            )
            db.commit()
        except Exception as task_error:
            db.rollback()
            task = db.get(ProcessingTask, task_id)
            if task is not None:
                task.status = "failed"
                task.step = "failed"
                if isinstance(task_error, NoQuestionsDetected):
                    task.error_message = str(task_error)
                else:
                    task.error_message = SAFE_AGENT_ERROR_MESSAGE
                assignment = db.get(Assignment, task.assignment_id)
                if assignment is not None:
                    assignment.status = "failed"
                    context.capabilities.audit.record(
                        db,
                        event_type="assignment.grading.failed",
                        actor_user_id=assignment.user_id,
                        outcome="failure",
                        resource_type="assignment",
                        resource_id=assignment.id,
                        summary="Assignment grading task failed",
                        metadata={"task_id": task.id, "subject": assignment.subject},
                        error_message=SAFE_AGENT_ERROR_MESSAGE,
                    )
                db.commit()


def persist_grade_payload(context: KernelContext, db: Session, assignment: Assignment, payload: ModelGradePayload) -> None:
    for item in payload.questions:
        point = item.knowledge_point.strip() if item.knowledge_point else None
        ensure_knowledge_point(db, assignment.subject, point)
        question = Question(
            assignment_id=assignment.id,
            question_number=item.question_number,
            content=item.question_text,
            student_answer=item.student_answer,
            correct_answer=item.correct_answer,
            question_type=item.question_type,
            knowledge_point=point,
            score=item.score,
            max_score=item.max_score,
            is_correct=item.is_correct,
            explanation=item.explanation,
            confidence=item.confidence,
            needs_review=item.confidence < context.settings.review_confidence_threshold,
        )
        db.add(question)
        db.flush()
        update_mastery(db, assignment.user_id, assignment.subject, point, item.is_correct)
        if not item.is_correct:
            upsert_wrong_question(
                db,
                user_id=assignment.user_id,
                question_id=question.id,
                subject=assignment.subject,
                knowledge_point=point,
                wrong_reason=item.explanation,
            )

    assignment.total_score = payload.total_score
    assignment.student_score = payload.student_score
    assignment.overall_comment = payload.overall_comment
    assignment.weak_points = payload.weak_points


async def update_and_regrade_question(
    context: KernelContext,
    db: Session,
    user: User,
    question: Question,
    patch: QuestionUpdateRequest,
) -> Question:
    assignment = question.assignment
    if assignment.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改该题目")

    old_point = question.knowledge_point
    old_is_correct = question.is_correct
    for field in ("content", "student_answer", "correct_answer", "knowledge_point"):
        value = getattr(patch, field)
        if value is not None:
            setattr(question, field, value.strip() if isinstance(value, str) else value)
    if question.knowledge_point:
        ensure_knowledge_point(db, assignment.subject, question.knowledge_point)

    result = await regrade_text_question(
        context,
        assignment.subject,
        question.content,
        question.student_answer,
        question.correct_answer,
        student_id=str(user.id),
    )
    question.is_correct = bool(result["is_correct"])
    question.score = float(result["score"])
    question.max_score = float(result["max_score"])
    question.explanation = str(result["explanation"])
    question.confidence = float(result["confidence"])
    question.needs_review = question.confidence < context.settings.review_confidence_threshold

    if old_is_correct is not None:
        update_mastery(db, user.id, assignment.subject, old_point, old_is_correct, delta=-1)
    update_mastery(db, user.id, assignment.subject, question.knowledge_point, question.is_correct)

    if question.is_correct:
        remove_wrong_question(db, question.id)
    else:
        upsert_wrong_question(
            db,
            user_id=user.id,
            question_id=question.id,
            subject=assignment.subject,
            knowledge_point=question.knowledge_point,
            wrong_reason=question.explanation,
        )

    context.capabilities.audit.record(
        db,
        event_type="assignment.question.regraded",
        actor=user,
        resource_type="question",
        resource_id=question.id,
        summary="Question corrected and regraded",
        metadata={
            "assignment_id": assignment.id,
            "subject": assignment.subject,
            "old_knowledge_point": old_point,
            "new_knowledge_point": question.knowledge_point,
            "old_is_correct": old_is_correct,
            "new_is_correct": question.is_correct,
            "needs_review": question.needs_review,
        },
    )
    db.flush()
    questions = db.scalars(select(Question).where(Question.assignment_id == assignment.id)).all()
    assignment.total_score = round(sum(item.max_score or 0 for item in questions), 1)
    assignment.student_score = round(sum(item.score or 0 for item in questions), 1)
    assignment.weak_points = list(
        dict.fromkeys(item.knowledge_point for item in questions if item.is_correct is False and item.knowledge_point)
    )
    db.commit()
    db.refresh(question)
    return question


def _set_task_state(task: ProcessingTask, assignment: Assignment, step: str, progress: int) -> None:
    task.status = "processing"
    task.step = step
    task.progress = progress
    assignment.status = "processing"
