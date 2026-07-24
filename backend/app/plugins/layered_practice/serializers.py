from app.plugins.layered_practice.models import PracticeTask


def serialize_practice(task: PracticeTask) -> dict:
    return {
        "id": task.id,
        "subject": task.subject,
        "knowledge_point": task.knowledge_point,
        "difficulty": task.difficulty,
        "question_count": task.question_count,
        "status": task.status,
        "student_score": task.student_score,
        "questions": [
            {
                "id": question.id,
                "question_number": question.question_number,
                "content": question.content,
                "standard_answer": question.standard_answer,
                "explanation": question.explanation,
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
        ],
    }
