import csv
from io import StringIO

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_admin
from app.kernel.audit.service import serialize_audit_log
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
def list_audit_logs(
    event_type: str | None = None,
    actor_username: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logs = get_kernel_context().capabilities.audit.list_all(
        db, limit=limit, offset=offset, event_type=event_type, actor_username=actor_username
    )
    return ok({"items": [serialize_audit_log(event) for event in logs], "offset": offset, "limit": limit})


@router.get("/export")
def export_audit_logs(
    request: Request,
    event_type: str | None = None,
    actor_username: str | None = None,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logs = get_kernel_context().capabilities.audit.list_all(
        db, limit=10_000, offset=0, event_type=event_type, actor_username=actor_username
    )
    content = StringIO()
    writer = csv.DictWriter(
        content,
        fieldnames=(
            "id", "created_at", "event_type", "outcome", "actor_user_id", "actor_username",
            "resource_type", "resource_id", "summary", "metadata", "error_message",
        ),
    )
    writer.writeheader()
    for event in logs:
        item = serialize_audit_log(event)
        item["metadata"] = str(item["metadata"])
        writer.writerow(item)
    get_kernel_context().capabilities.audit.record(
        db,
        event_type="admin.audit.exported",
        actor=admin,
        resource_type="audit_log",
        resource_id="export",
        summary="Administrator exported audit logs",
        metadata={"event_type": event_type, "actor_username": actor_username, "count": len(logs)},
        request=request,
        commit=True,
    )
    filename = "audit-logs.csv"
    return StreamingResponse(
        iter([content.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
