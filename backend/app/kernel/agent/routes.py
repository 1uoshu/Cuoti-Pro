"""Agent HTTP routes -- sessions, messages, upload, replay, address suggestions."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.chat.service import (
    add_message,
    create_session,
    delete_session,
    get_session,
    list_messages,
    list_sessions,
    rename_session,
    serialize_message,
    serialize_session,
)
from app.kernel.context import get_kernel_context
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok

router = APIRouter(tags=["agent"])


# ── 会话 CRUD ──────────────────────────────────────────────────────


@router.post("/agent/sessions")
def create_chat_session(
    title: str = "新对话",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = create_session(db, user_id=user.id, title=title)
    return ok(serialize_session(session))


@router.get("/agent/sessions")
def list_chat_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = list_sessions(db, user_id=user.id)
    return ok([serialize_session(s) for s in sessions])


@router.patch("/agent/sessions/{session_id}")
def rename_chat_session(
    session_id: int,
    title: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = rename_session(db, session_id=session_id, user_id=user.id, title=title)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ok(serialize_session(session))


@router.delete("/agent/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not delete_session(db, session_id=session_id, user_id=user.id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return ok({"deleted": True})


# ── 消息 ──────────────────────────────────────────────────────────


@router.get("/agent/sessions/{session_id}/messages")
def list_chat_messages(
    session_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = list_messages(db, session_id=session_id, user_id=user.id, limit=limit, offset=offset)
    return ok([serialize_message(m) for m in messages])


@router.post("/agent/sessions/{session_id}/messages")
def send_message_http(
    session_id: int,
    content: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HTTP fallback for sending a message (when WS is unavailable)."""
    session = get_session(db, session_id=session_id, user_id=user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    msg = add_message(db, session_id=session_id, role="student", content=content)
    # TODO: 触发 Agent runtime 处理（后续集成）
    return ok(serialize_message(msg))


# ── 上传 ──────────────────────────────────────────────────────────


@router.post("/agent/upload")
async def upload_for_grading(
    file: UploadFile = File(...),
    subject: str = Form(...),
    title: str | None = Form(default=None),
    session_id: int | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """chat 内上传作业，返回 assignment_id + task_id."""
    context = get_kernel_context()
    from app.plugins.assignment_grading.service import create_assignment

    assignment, task = await create_assignment(context, db, user, file, subject, title)

    # 如果提供了 session_id，记录上传消息
    if session_id:
        add_message(
            db,
            session_id=session_id,
            role="student",
            content=f"上传了作业：{assignment.title}",
            card_type="uploading",
            card_payload={
                "assignment_id": assignment.id,
                "task_id": task.id,
                "subject": subject,
            },
        )

    return ok({
        "assignment_id": assignment.id,
        "task_id": task.id,
        "status": "queued",
    })


# ── 回放 ──────────────────────────────────────────────────────────


@router.get("/agent/sessions/{session_id}/replay")
def replay_events(
    session_id: int,
    since: str | None = Query(default=None, description="从哪个 event_id 之后开始回放"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """断线重连回放."""
    session = get_session(db, session_id=session_id, user_id=user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    context = get_kernel_context()
    event_bus = context.capabilities.agent_runtime._event_bus
    if event_bus is None:
        return ok([])

    events = event_bus.replay(str(session_id), since)
    return ok([
        {
            "type": e.type.value,
            "step_id": e.step_id,
            "data": e.data,
            "event_id": e.event_id,
            "timestamp": e.timestamp,
        }
        for e in events
    ])


# ── Tab 联想 ──────────────────────────────────────────────────────


@router.get("/agent/address-suggestions")
def address_suggestions(
    prefix: str = Query(default="", description="Plugin::Tool 前缀"),
    user: User = Depends(get_current_user),
):
    """Tab 联想：返回匹配前缀的工具列表."""
    context = get_kernel_context()
    tools = context.capabilities.tool_registry.list_all()

    filtered = [
        {
            "name": t.name,
            "short_intent": t.short_intent,
            "side_effect": t.side_effect.value,
            "description": t.description,
        }
        for t in tools
        if not prefix
        or t.name.lower().startswith(prefix.lower())
        or prefix.lower() in t.short_intent.lower()
    ]
    return ok(filtered)
