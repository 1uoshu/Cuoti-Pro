from app.plugins.stage_assessment.models import ExamTask


def serialize_exam(task: ExamTask, *, include_questions: bool = False) -> dict:
    data = {
        "id": task.id,
        "title": task.title,
        "subject": task.subject,
        "exam_type": task.exam_type,
        "status": task.status,
        "question_count": task.question_count,
        "estimated_minutes": task.question_count * 2,
        "student_score": task.student_score,
        "created_at": task.created_at,
    }
    if include_questions:
        data["questions"] = [
            {
                "id": question.id,
                "question_number": question.question_number,
                "content": question.content,
                "standard_answer": question.standard_answer,
                "explanation": question.explanation,
                "knowledge_point": question.knowledge_point,
                "confidence": question.confidence,
                "confidence_warning": question.confidence_warning,
                "answers": [
                    {
                        "answer": answer.answer,
                        "is_correct": answer.is_correct,
                        "score": answer.score,
                        "explanation": answer.explanation,
                        "confidence": answer.confidence,
                        "confidence_warning": answer.confidence_warning,
                    }
                    for answer in question.answers
                ],
            }
            for question in task.questions
        ]
    return data
