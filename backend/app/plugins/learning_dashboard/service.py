from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.kernel.models import User
from app.plugins.assignment_grading.models import Assignment
from app.plugins.mastery_tracking.models import MasteryRecord
from app.plugins.wrong_question_book.models import WrongQuestion


def get_dashboard(db: Session, user: User) -> dict:
    assignment_count = db.scalar(select(func.count()).select_from(Assignment).where(Assignment.user_id == user.id)) or 0
    wrong_count = db.scalar(select(func.count()).select_from(WrongQuestion).where(WrongQuestion.user_id == user.id)) or 0
    mastery = db.scalars(
        select(MasteryRecord)
        .where(MasteryRecord.user_id == user.id)
        .order_by(MasteryRecord.mastery_score.asc())
        .limit(5)
    ).all()
    return {
        "assignment_count": assignment_count,
        "wrong_count": wrong_count,
        "weak_points": [
            {"subject": item.subject, "knowledge_point": item.knowledge_point, "mastery_score": item.mastery_score}
            for item in mastery
        ],
    }
