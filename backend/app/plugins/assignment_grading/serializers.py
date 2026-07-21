from app.plugins.assignment_grading.models import Assignment, ProcessingTask, Question


def serialize_question(question: Question) -> dict:
    return {
        "id": question.id,
        "question_number": question.question_number,
        "content": question.content,
        "student_answer": question.student_answer,
        "correct_answer": question.correct_answer,
        "question_type": question.question_type,
        "knowledge_point": question.knowledge_point,
        "score": question.score,
        "max_score": question.max_score,
        "is_correct": question.is_correct,
        "explanation": question.explanation,
        "confidence": question.confidence,
        "needs_review": question.needs_review,
    }


def serialize_task(task: ProcessingTask) -> dict:
    return {
        "id": task.id,
        "status": task.status,
        "step": task.step,
        "progress": task.progress,
        "error_message": task.error_message,
    }


def serialize_assignment(assignment: Assignment, include_questions: bool = False) -> dict:
    data = {
        "id": assignment.id,
        "title": assignment.title,
        "subject": assignment.subject,
        "status": assignment.status,
        "total_score": assignment.total_score,
        "student_score": assignment.student_score,
        "overall_comment": assignment.overall_comment,
        "weak_points": assignment.weak_points or [],
        "created_at": assignment.created_at,
    }
    if assignment.task:
        data["task"] = serialize_task(assignment.task)
    if include_questions:
        data["questions"] = [serialize_question(question) for question in assignment.questions]
    return data
