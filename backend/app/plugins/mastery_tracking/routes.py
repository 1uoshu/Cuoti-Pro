from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.mastery_tracking.models import MasteryRecord
from app.plugins.mastery_tracking.service import serialize_mastery


router = APIRouter(tags=["mastery"])


@router.get("/mastery")
def mastery(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    records = db.scalars(
        select(MasteryRecord)
        .where(MasteryRecord.user_id == user.id)
        .order_by(MasteryRecord.mastery_score.asc())
    ).all()
    return ok([serialize_mastery(record) for record in records])
