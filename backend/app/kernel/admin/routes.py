from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.admin.schemas import RuntimeConfigUpdateRequest
from app.kernel.admin.service import serialize_runtime_settings, update_runtime_settings
from app.kernel.auth.dependencies import get_current_admin
from app.kernel.auth.services import serialize_user
from app.kernel.auth.sessions import revoke_all_user_tokens
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    users = db.scalars(select(User).order_by(User.id).offset(offset).limit(limit)).all()
    return ok({"items": [serialize_user(user) for user in users], "offset": offset, "limit": limit})


@router.post("/users/{user_id}/revoke-sessions")
def revoke_user_sessions(
    user_id: int,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    revoke_all_user_tokens(get_kernel_context().capabilities.redis, user.id)
    get_kernel_context().capabilities.audit.record(
        db,
        event_type="admin.user.sessions.revoked",
        actor=admin,
        resource_type="user",
        resource_id=user.id,
        summary="Administrator revoked user sessions",
        request=request,
        commit=True,
    )
    return ok({"user_id": user.id, "sessions_revoked": True})


@router.get("/config")
def get_runtime_config(_: User = Depends(get_current_admin)):
    return ok(serialize_runtime_settings(get_kernel_context().settings))


@router.put("/config")
def update_runtime_config(
    payload: RuntimeConfigUpdateRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True, mode="json")
    changed_fields = update_runtime_settings(db, get_kernel_context().settings, updates)
    if not changed_fields:
        raise HTTPException(status_code=400, detail="至少提供一个可更新配置")
    get_kernel_context().capabilities.audit.record(
        db,
        event_type="admin.config.updated",
        actor=admin,
        resource_type="runtime_config",
        resource_id="kernel",
        summary="Administrator updated runtime configuration",
        metadata={"changed_fields": changed_fields},
        request=request,
    )
    db.commit()
    return ok(serialize_runtime_settings(get_kernel_context().settings))
