from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.plugins.learning_dashboard.service import get_dashboard


router = APIRouter(tags=["learning-dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(get_dashboard(db, user))
