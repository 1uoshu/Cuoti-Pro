from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.kernel.auth.dependencies import get_current_user
from app.kernel.database import get_db
from app.kernel.models import User
from app.kernel.responses import ok
from app.kernel.storage import UploadStorage
from app.plugins.agent_chat.schemas import (
    MessageOut,
    ReplayOut,
    ReviewConfirmRequest,
    SessionCreate,
    SessionOut,
    SessionPatch,
    TextMessageRequest,
    UnifiedMessageOut,
)
from app.plugins.agent_chat.service import (
    add_message,
    create_session,
    delete_session,
    get_messages_since,
    get_session,
    list_messages,
    list_sessions,
    update_session,
    update_message_card,
)

router = APIRouter(tags=["agent-chat"])


# ── 会话管理 ──────────────────────────────────────

@router.post("/agent/sessions")
def api_create_session(
    body: SessionCreate | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = body.title if body else None
    session = create_session(db, user.id, title)
    return ok(SessionOut.model_validate(session).model_dump())


@router.get("/agent/sessions")
def api_list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = list_sessions(db, user.id)
    return ok([SessionOut.model_validate(s).model_dump() for s in sessions])


@router.patch("/agent/sessions/{session_id}")
def api_update_session(
    session_id: str,
    body: SessionPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = update_session(db, session_id, user.id, body.title)
    return ok(SessionOut.model_validate(session).model_dump())


@router.delete("/agent/sessions/{session_id}")
def api_delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_session(db, session_id, user.id)
    return ok({"deleted": True})


# ── 消息 ──────────────────────────────────────────

@router.get("/agent/sessions/{session_id}/messages")
def api_list_messages(
    session_id: str,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = list_messages(db, session_id, user.id, limit)
    return ok([MessageOut.model_validate(m).model_dump() for m in messages])


@router.post("/agent/sessions/{session_id}/messages")
def api_send_text_message(
    session_id: str,
    body: TextMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HTTP fallback 通道：发送文本消息给 Agent。"""
    get_session(db, session_id, user.id)  # 校验归属

    # 插入学生消息
    student_msg = add_message(db, session_id, "student", body.content)

    # TODO: 接入 Agent 运行时进行意图识别和回复生成
    # 当前先返回一个占位回复
    agent_msg = add_message(
        db,
        session_id,
        "agent",
        "收到你的消息，Agent 运行时正在开发中。",
        step_id=f"step_{student_msg.id}",
    )

    return ok({
        "student_message": MessageOut.model_validate(student_msg).model_dump(),
        "agent_message": MessageOut.model_validate(agent_msg).model_dump(),
    })


@router.get("/agent/sessions/{session_id}/replay")
def api_replay(
    session_id: str,
    since: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = get_messages_since(db, session_id, user.id, since)
    return ok(ReplayOut(
        replay_from=since,
        messages=[MessageOut.model_validate(m).model_dump() for m in messages],
        pending_events=[],  # TODO: 从 Redis Streams 读取
    ).model_dump())


# ── 统一消息入口（文件+文字）───────────────────────

@router.post("/agent/messages")
def api_unified_message(
    content: str | None = Form(None),
    subject: str | None = Form(None),
    session_id: str | None = Form(None),
    file: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """统一消息入口：支持只发文字、只发文件、文件+文字。"""
    if not content and not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content 和 file 至少提供一个")

    # 如果没有指定会话，自动创建
    if session_id:
        get_session(db, session_id, user.id)  # 校验归属
    else:
        session = create_session(db, user.id)
        session_id = session.id

    # 组装学生消息文本
    message_parts = []
    if content:
        message_parts.append(content)
    if file:
        message_parts.append(f"[附件: {file.filename}]")
    message_text = "\n".join(message_parts)

    # 插入学生消息
    student_msg = add_message(db, session_id, "student", message_text)

    # TODO: 根据是否有文件，进入不同的 Agent 处理流程
    # 有文件 → 保存文件 → Agent 意图识别 → 可能调批改工具
    # 无文件 → Agent 意图识别 → 流式文字回复
    has_file = file is not None

    return ok(UnifiedMessageOut(
        message_id=student_msg.id,
        session_id=session_id,
        has_file=has_file,
        assignment_id=None,  # TODO: 触发批改时返回
        task_id=None,        # TODO: 触发批改时返回
    ).model_dump())


# ── 兼容旧接口：文件上传 ──────────────────────────

@router.post("/agent/upload")
async def api_upload_file(
    file: UploadFile = File(...),
    subject: str = Form(...),
    title: str | None = Form(None),
    session_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """兼容前端的 /api/agent/upload 接口，保存文件并记录路径。"""
    from app.kernel.context import get_kernel_context
    context = get_kernel_context()

    # 保存文件到磁盘
    file_path, suffix = await context.capabilities.storage.save_upload(file, user.id, "uploads")

    # 如果没有指定会话，自动创建
    if session_id:
        get_session(db, session_id, user.id)
    else:
        session = create_session(db, user.id)
        session_id = session.id

    # 组装学生消息，把文件路径存在 card_payload 里
    message_text = f"[附件: {file.filename}]"
    if title:
        message_text = f"{title}\n{message_text}"

    student_msg = add_message(
        db, session_id, "student", message_text,
        card_payload={
            "file_path": file_path,
            "file_suffix": suffix,
            "subject": subject,
            "original_filename": file.filename,
        },
    )

    return ok({
        "message_id": student_msg.id,
        "session_id": session_id,
        "has_file": True,
        "assignment_id": None,
        "task_id": None,
    })


# ── 待复核确认 ────────────────────────────────────

@router.post("/agent/sessions/{session_id}/review-confirm")
def api_review_confirm(
    session_id: str,
    body: ReviewConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """待复核题目确认归档。"""
    get_session(db, session_id, user.id)  # 校验归属

    # TODO: 接入 WrongQuestionBook 服务，校验 needs_review=true 后归档
    # 当前先返回占位结果
    return ok({
        "confirmed_count": len(body.question_ids),
        "archived_question_ids": body.question_ids,
    })
