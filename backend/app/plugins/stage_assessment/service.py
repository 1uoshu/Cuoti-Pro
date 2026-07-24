from sqlalchemy import select
from collections import defaultdict

from sqlalchemy.orm import Session, selectinload

from app.kernel.context import KernelContext
from fastapi import HTTPException, status
from app.kernel.models import User
from app.kernel.responses import SAFE_AGENT_ERROR_MESSAGE
from app.plugins.layered_practice.schemas import PracticeSubmitRequest
from app.plugins.layered_practice.workflow import grade_practice_answer
from app.plugins.mastery_tracking.models import KnowledgePoint
from app.plugins.mastery_tracking.service import ensure_knowledge_point, update_mastery
from app.plugins.stage_assessment.models import ExamAnswer, ExamQuestion, ExamTask
from app.plugins.stage_assessment.schemas import ExamCreateRequest
from app.plugins.stage_assessment.workflow import generate_exam_questions
from app.plugins.wrong_question_book.service import get_recent_mistakes


async def create_exam_task(
    context: KernelContext,
    db: Session,
    user: User,
    request: ExamCreateRequest,
) -> ExamTask:
    knowledge_points = _resolve_knowledge_points(db, request.subject, request.knowledge_points)
    for point in knowledge_points:
        ensure_knowledge_point(db, request.subject, point)
    task = ExamTask(
        user_id=user.id,
        title=f"{request.subject}·阶段评估试卷",
        subject=request.subject,
        exam_type=request.exam_type,
        knowledge_points=knowledge_points,
        difficulty=request.difficulty,
        question_count=request.question_count,
        status="generating",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        recent_mistakes = [
            mistake
            for point in knowledge_points
            for mistake in get_recent_mistakes(db, user.id, request.subject, point)
        ][:10]
        payload = await generate_exam_questions(
            context,
            grade=user.grade,
            subject=request.subject,
            exam_type=request.exam_type,
            knowledge_points=knowledge_points,
            difficulty=request.difficulty,
            count=request.question_count,
            recent_mistakes=recent_mistakes,
        )
        for index, item in enumerate(payload.questions, start=1):
            db.add(
                ExamQuestion(
                    exam_task_id=task.id,
                    question_number=index,
                    content=item.content,
                    standard_answer=item.standard_answer,
                    explanation=item.explanation,
                    knowledge_point=item.knowledge_point,
                    confidence=item.confidence,
                    confidence_warning=item.confidence_warning,
                )
            )
        task.status = "ready"
        context.capabilities.audit.record(
            db,
            event_type="exam.generated",
            actor=user,
            resource_type="exam_task",
            resource_id=task.id,
            summary="Stage assessment generated",
            metadata={
                "subject": task.subject,
                "exam_type": task.exam_type,
                "question_count": task.question_count,
            },
        )
        db.commit()
        db.refresh(task)
        return task
    except Exception:
        db.rollback()
        task = db.get(ExamTask, task.id)
        if task is not None:
            task.status = "failed"
            context.capabilities.audit.record(
                db,
                event_type="exam.generation.failed",
                actor=user,
                outcome="failure",
                resource_type="exam_task",
                resource_id=task.id,
                summary="Stage assessment generation failed",
                error_message=SAFE_AGENT_ERROR_MESSAGE,
            )
            db.commit()
        raise


def _resolve_knowledge_points(db: Session, subject: str, requested: list[str]) -> list[str]:
    if requested and requested != ["all"]:
        return requested
    points = db.scalars(
        select(KnowledgePoint.name)
        .where(KnowledgePoint.subject == subject)
        .order_by(KnowledgePoint.name)
    ).all()
    return list(dict.fromkeys(points)) or ["综合能力"]


async def submit_exam_answers(
    context: KernelContext,
    db: Session,
    user: User,
    task: ExamTask,
    request: PracticeSubmitRequest,
) -> ExamTask:
    if task.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权提交该考核")
    question_map = {question.id: question for question in task.questions}
    submitted_ids = {answer.question_id for answer in request.answers}
    if len(request.answers) != len(question_map) or submitted_ids != set(question_map):
        raise HTTPException(status_code=400, detail="请完成并提交所有考核题目")

    total_score = 0.0
    for input_answer in request.answers:
        question = question_map[input_answer.question_id]
        result = await grade_practice_answer(
            context,
            str(user.id),
            task.subject,
            {"content": question.content, "standard_answer": question.standard_answer},
            input_answer.answer,
        )
        raw_score = float(result["score"])
        raw_max_score = float(result["max_score"])
        if raw_max_score <= 0:
            raise ValueError("exam grading max_score must be positive")
        score = round(min(max(raw_score / raw_max_score * 10, 0), 10), 2)
        is_correct = bool(result["is_correct"])
        confidence = float(result["confidence"])
        total_score += score
        db.add(
            ExamAnswer(
                exam_question_id=question.id,
                answer=input_answer.answer,
                is_correct=is_correct,
                score=score,
                explanation=str(result["explanation"]),
                confidence=confidence,
                confidence_warning=(
                    "判题置信度偏低，请结合题目与解析自行判断"
                    if confidence < context.settings.review_confidence_threshold
                    else None
                ),
            )
        )
        update_mastery(db, user.id, task.subject, question.knowledge_point, is_correct)

    task.student_score = round(total_score / (len(question_map) * 10) * 100, 1) if question_map else 0
    task.status = "completed"
    context.capabilities.audit.record(
        db,
        event_type="exam.submitted",
        actor=user,
        resource_type="exam_task",
        resource_id=task.id,
        summary="Stage assessment answers submitted",
        metadata={
            "subject": task.subject,
            "exam_type": task.exam_type,
            "question_count": len(question_map),
            "student_score": task.student_score,
        },
    )
    db.commit()
    db.refresh(task)
    return task


def get_score_compare(db: Session, user_id: int, subject: str | None) -> dict:
    query = (
        select(ExamTask)
        .options(selectinload(ExamTask.questions).selectinload(ExamQuestion.answers))
        .where(ExamTask.user_id == user_id, ExamTask.status == "completed")
        .order_by(ExamTask.created_at.desc(), ExamTask.id.desc())
        .limit(2)
    )
    if subject:
        query = query.where(ExamTask.subject == subject)
    tasks = db.scalars(query).all()
    if not tasks:
        return {"last_score": None, "current_score": None, "improvement": 0, "mastery_changes": []}

    current = tasks[0]
    current_score = round(current.student_score or 0, 1)
    if len(tasks) == 1:
        return {
            "last_score": None,
            "current_score": current_score,
            "improvement": 0,
            "mastery_changes": [],
        }

    previous = tasks[1]
    previous_score = round(previous.student_score or 0, 1)
    previous_mastery = _exam_mastery(previous)
    current_mastery = _exam_mastery(current)
    mastery_changes = [
        {
            "knowledge_point": point,
            "previous": previous_mastery.get(point, 0),
            "current": current_mastery.get(point, 0),
            "change": round(current_mastery.get(point, 0) - previous_mastery.get(point, 0)),
        }
        for point in sorted(set(previous_mastery) | set(current_mastery))
    ]
    return {
        "last_score": previous_score,
        "current_score": current_score,
        "improvement": round(current_score - previous_score, 1),
        "mastery_changes": mastery_changes,
    }


def _exam_mastery(task: ExamTask) -> dict[str, int]:
    outcomes: dict[str, list[bool]] = defaultdict(list)
    for question in task.questions:
        if question.answers:
            outcomes[question.knowledge_point].append(question.answers[-1].is_correct)
    return {
        point: round(sum(results) / len(results) * 100)
        for point, results in outcomes.items()
    }
