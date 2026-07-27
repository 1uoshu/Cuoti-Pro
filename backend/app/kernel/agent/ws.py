"""WebSocket endpoint for Agent chat — /api/agent/ws."""

from __future__ import annotations

import json
import sys
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.kernel.agent.events import (
    emit_intent_recognized,
    emit_plan_done,
    emit_plan_start,
    emit_session_end,
    emit_session_welcome,
    emit_text_delta,
    emit_tool_call,
)
from app.kernel.agent.intent_router import INTENT_GENERAL_CHAT, INTENT_HOMEWORK_GRADING, INTENT_TOOL_MAP
from app.kernel.agent.runtime import AgentRuntime
from app.kernel.auth.security import decode_access_token
from app.kernel.context import get_kernel_context
from app.kernel.database import SessionLocal
from app.kernel.models import User
from app.plugins.agent_chat.models import ChatMessage, ChatSession
from app.plugins.agent_chat.service import add_message

router = APIRouter(tags=["agent-ws"])


class ConnectionManager:
    """Manages active WebSocket connections per session."""

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[session_id] = ws

    def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        return self._connections.get(session_id)


manager = ConnectionManager()


@router.websocket("/agent/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "", token: str = ""):
    """WebSocket endpoint for Agent chat.

    Connect: ws://<host>/api/agent/ws?session_id=<uuid>&token=<jwt>
    """
    # 1. Validate JWT
    if not token:
        await websocket.close(code=4001, reason="缺少 token")
        return

    try:
        access_token = decode_access_token(token)
    except Exception:
        await websocket.close(code=4001, reason="JWT 无效或过期")
        return

    user_id = access_token.user_id

    # 2. Validate session ownership
    if not session_id:
        await websocket.close(code=4003, reason="缺少 session_id")
        return

    with SessionLocal() as db:
        session = db.get(ChatSession, session_id)
        if session is None:
            await websocket.close(code=4003, reason="会话不存在")
            return
        if session.user_id != user_id:
            await websocket.close(code=4003, reason="无权访问该会话")
            return
        session_title = session.title

    # 3. Accept connection
    await manager.connect(session_id, websocket)

    try:
        # 4. Send welcome event
        await emit_session_welcome(
            websocket, session_id,
            replay_from_step_id=None,  # TODO: 从 Redis Streams 获取
            session_title=session_title,
        )

        # 5. Message loop
        while True:
            try:
                raw = await websocket.receive_text()
            except Exception as recv_err:
                print(f"[WS] receive_text error: {recv_err}", file=sys.stderr, flush=True)
                break
            print(f"[WS] Got raw: {raw[:300]}", file=sys.stderr, flush=True)
            await _handle_client_message(raw, session_id, user_id, websocket)

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="服务端异常")
        except Exception:
            pass
    finally:
        manager.disconnect(session_id)


async def _handle_client_message(raw: str, session_id: str, user_id: int, ws: WebSocket):
    """Handle a message from the WebSocket client."""
    import sys
    print(f"[WS] Received raw message: {raw[:200]}", file=sys.stderr, flush=True)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return

    msg_type = data.get("type")
    content = data.get("content", "")

    if msg_type not in ("chat.send", "chat.message") or not content:
        print(f"[WS] Ignored message type={msg_type}, content_len={len(content)}", file=sys.stderr, flush=True)
        return

    print(f"[WS] Processing message type={msg_type}, content={content[:100]}", file=sys.stderr, flush=True)

    context = get_kernel_context()

    with SessionLocal() as db:
        # 1. 检查最近是否有刚上传的文件消息（避免重复存储）
        latest_upload = db.scalar(
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "student")
            .order_by(ChatMessage.created_at.desc())
        )
        has_recent_upload = (
            latest_upload
            and latest_upload.card_payload
            and latest_upload.card_payload.get("file_path")
        )

        if has_recent_upload:
            # 已有上传消息，不重复创建学生消息
            student_msg = latest_upload
        else:
            # 纯文字消息，创建新的学生消息
            student_msg = add_message(db, session_id, "student", content)

        # 2. Load student profile
        user = db.get(User, user_id)
        student_profile = {
            "grade": user.grade if user else None,
            "main_subject": user.main_subject if user else None,
        }

        # 3. Load message history
        messages = list(
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(20)
            .all()
        )
        message_dicts = [{"role": m.role, "content": m.content} for m in messages]

        # 4. 查找最近上传的文件（从 card_payload 中获取 file_path）
        file_path = None
        file_data_url = None
        for msg in reversed(messages):
            if msg.card_payload and msg.card_payload.get("file_path"):
                file_path = msg.card_payload["file_path"]
                break

    # 5. 如果有文件，转为 dataurl 供视觉 LLM 使用
    if file_path:
        try:
            from app.plugins.assignment_grading.workflow import _load_upload_as_data_urls
            urls = _load_upload_as_data_urls(file_path)
            if urls:
                file_data_url = urls[0]  # 取第一张图
        except Exception as e:
            print(f"[WS] Failed to load file as dataurl: {e}", file=sys.stderr, flush=True)

    # 4. Run Agent
    plan_id = f"plan_{uuid.uuid4().hex[:12]}"

    try:
        await emit_plan_start(ws, session_id, plan_id, goal="处理学生消息")
    except Exception:
        pass  # WebSocket 可能已断，不影响后续处理

    try:
        # Build initial state
        student_text = content if not has_recent_upload else content

        state = {
            "session_id": session_id,
            "user_id": user_id,
            "student_message": student_text,
            "file_path": file_path,
            "file_data_url": file_data_url,
            "file_content": None,
            "messages": message_dicts,
            "student_profile": student_profile,
        }

        # Run the LangGraph workflow
        runtime = context.capabilities.agent_runtime
        workflow = runtime.compile_agent_workflow()
        result = await workflow.ainvoke(state)

        intent = result.get("intent", INTENT_GENERAL_CHAT)
        intent_confidence = result.get("intent_confidence", 0.5)
        intent_description = result.get("intent_description", "")
        tool_to_call = result.get("tool_to_call")
        llm_response = result.get("llm_response", "收到你的消息。")
        file_content = result.get("file_content")

        # 5. 如果有图片描述，把学生消息内容替换为图片描述（让 LLM 直接看到题目）
        if file_content and has_recent_upload:
            with SessionLocal() as db:
                msg = db.get(ChatMessage, student_msg.id)
                if msg:
                    msg.content = f"[附件内容：{file_content}]"
                    if content and content != '[用户上传了文件，未附带文字说明]':
                        msg.content = f"{content}\n{msg.content}"
                    db.commit()

        # 6. 先把结果存数据库（不管 WebSocket 是否还在）
        with SessionLocal() as db:
            add_message(db, session_id, "agent", llm_response, step_id=plan_id)

        # 6. 尝试通过 WebSocket 推送事件（断了就跳过）
        try:
            await emit_intent_recognized(
                ws, session_id,
                intent=intent,
                confidence=intent_confidence,
                description=intent_description,
                has_file=bool(result.get("file_path")),
                tool_to_call=tool_to_call,
            )
            if tool_to_call:
                await emit_tool_call(
                    ws, session_id,
                    tool_address=tool_to_call,
                    proposal=f"我将调用 {tool_to_call} 来处理你的请求。",
                    source="agent",
                    side_effect="write" if "Grading" in tool_to_call or "Archive" in tool_to_call else "read",
                )
            await emit_text_delta(ws, session_id, delta=llm_response, accumulated=llm_response)
            await emit_plan_done(ws, session_id, plan_id, success=True, summary=llm_response[:100])
        except Exception:
            pass  # WebSocket 已断，结果已在数据库，用户切回来能看到

    except Exception as exc:
        import traceback
        traceback.print_exc()
        error_msg = "抱歉，处理你的消息时出现了问题，请稍后再试。"
        with SessionLocal() as db:
            add_message(db, session_id, "agent", error_msg, step_id=plan_id)


def get_connection_manager() -> ConnectionManager:
    return manager
