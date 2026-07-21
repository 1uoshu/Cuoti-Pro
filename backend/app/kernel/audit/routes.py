from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.audit.service import serialize_audit_log
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/me")
def my_audit_logs(
    event_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logs = get_kernel_context().capabilities.audit.list_for_user(db, user.id, limit=limit, event_type=event_type)
    return ok([serialize_audit_log(event) for event in logs])
