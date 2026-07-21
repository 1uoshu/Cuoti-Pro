from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.wrong_question_book.service import list_wrong_questions


router = APIRouter(tags=["wrong-question-book"])


@router.get("/wrong-questions")
def wrong_questions(subject: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_wrong_questions(db, user.id, subject))
