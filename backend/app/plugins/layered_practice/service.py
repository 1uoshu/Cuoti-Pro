from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.context import KernelContext
from app.kernel.models import User
from app.plugins.layered_practice.models import PracticeAnswer, PracticeQuestion, PracticeTask
from app.plugins.layered_practice.schemas import PracticeCreateRequest, PracticeSubmitRequest
from app.plugins.layered_practice.workflow import generate_practice_questions, grade_practice_answer
from app.plugins.mastery_tracking.service import ensure_knowledge_point, update_mastery
from app.plugins.wrong_question_book.service import get_recent_mistakes


async def create_practice_task(context: KernelContext, db: Session, user: User, request: PracticeCreateRequest) -> PracticeTask:
    ensure_knowledge_point(db, request.subject, request.knowledge_point)
    task = PracticeTask(
        user_id=user.id,
        subject=request.subject,
        knowledge_point=request.knowledge_point,
        difficulty=request.difficulty,
        question_count=request.question_count,
        status="generating",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        payload = await generate_practice_questions(
            context,
            str(user.id),
            request.subject,
            user.grade,
            request.knowledge_point,
            request.difficulty,
            request.question_count,
            get_recent_mistakes(db, user.id, request.subject, request.knowledge_point),
        )
        for index, item in enumerate(payload.questions, start=1):
            db.add(
                PracticeQuestion(
                    practice_task_id=task.id,
                    question_number=index,
                    content=item.content,
                    standard_answer=item.standard_answer,
                    explanation=item.explanation,
                    confidence=item.confidence,
                    confidence_warning=(
                        item.confidence_warning
                        or (
                            "题目与答案的验算置信度偏低，请结合解析自行判断"
                            if item.confidence < context.settings.review_confidence_threshold
                            else None
                        )
                    ),
                )
            )
        task.status = "ready"
        context.capabilities.audit.record(
            db,
            event_type="practice.generated",
            actor=user,
            resource_type="practice_task",
            resource_id=task.id,
            summary="Layered practice task generated",
            metadata={
                "subject": task.subject,
                "knowledge_point": task.knowledge_point,
                "difficulty": task.difficulty,
                "question_count": task.question_count,
            },
        )
        db.commit()
        db.refresh(task)
        return task
    except Exception as error:
        task.status = "failed"
        context.capabilities.audit.record(
            db,
            event_type="practice.generation.failed",
            actor=user,
            outcome="failure",
            resource_type="practice_task",
            resource_id=task.id,
            summary="Layered practice generation failed",
            metadata={
                "subject": task.subject,
                "knowledge_point": task.knowledge_point,
                "difficulty": task.difficulty,
            },
            error_message=str(error),
        )
        db.commit()
        raise


async def submit_practice_answers(
    context: KernelContext,
    db: Session,
    user: User,
    task: PracticeTask,
    request: PracticeSubmitRequest,
) -> PracticeTask:
    if task.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权提交该练习")
    question_map = {question.id: question for question in task.questions}
    submitted_ids = {answer.question_id for answer in request.answers}
    if len(request.answers) != len(question_map) or submitted_ids != set(question_map):
        raise HTTPException(status_code=400, detail="请完成并提交所有练习题")

    total_score = 0.0
    max_score = float(len(question_map) * 10)
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
        score = round(min(raw_score / raw_max_score * 10, 10.0), 2)
        total_score += score
        db.add(
            PracticeAnswer(
                practice_question_id=question.id,
                answer=input_answer.answer,
                is_correct=bool(result["is_correct"]),
                score=score,
                explanation=str(result["explanation"]),
                confidence=float(result["confidence"]),
                confidence_warning=(
                    "判题置信度偏低，请结合题目与解析自行判断"
                    if float(result["confidence"]) < context.settings.review_confidence_threshold
                    else None
                ),
            )
        )
        update_mastery(db, user.id, task.subject, task.knowledge_point, bool(result["is_correct"]))

    task.student_score = round(total_score / max_score * 100, 1) if max_score else 0
    task.status = "completed"
    context.capabilities.audit.record(
        db,
        event_type="practice.submitted",
        actor=user,
        resource_type="practice_task",
        resource_id=task.id,
        summary="Layered practice answers submitted",
        metadata={
            "subject": task.subject,
            "knowledge_point": task.knowledge_point,
            "difficulty": task.difficulty,
            "question_count": len(question_map),
            "student_score": task.student_score,
        },
    )
    db.commit()
    db.refresh(task)
    return task
