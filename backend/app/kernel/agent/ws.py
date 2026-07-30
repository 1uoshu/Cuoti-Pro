"""WebSocket endpoint for Agent real-time communication."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.kernel.auth.security import decode_access_token
from app.kernel.auth.sessions import token_is_active
from app.kernel.chat.service import add_message, list_messages
from app.kernel.agent.context import convert_history_to_api
from app.kernel.context import get_kernel_context
from app.kernel.database import SessionLocal

ws_router = APIRouter(tags=["agent-ws"])


@ws_router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    session_id: int = Query(...),
):
    """WebSocket endpoint -- JWT auth + event stream.

    Flow:
    1. Validate JWT token
    2. Send session.welcome (with replay hint)
    3. Receive student message -> load history -> call runtime.run_turn()
    4. Background task: poll EventBus -> forward events to WebSocket
    """
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Validate JWT
    try:
        access_token = decode_access_token(token)
        user_id = access_token.user_id
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Check token is still whitelisted in Redis
    context = get_kernel_context()
    if not token_is_active(context.capabilities.redis, access_token):
        await websocket.close(code=4001, reason="Token revoked")
        return

    await websocket.accept()

    runtime = context.capabilities.agent_runtime
    event_bus = runtime._event_bus

    # Send session.welcome with replay hint
    latest_event_id = event_bus.get_latest_event_id(str(session_id)) if event_bus else None
    await websocket.send_json({
        "type": "session.welcome",
        "session_id": str(session_id),
        "data": {"replay_from_step_id": latest_event_id},
    })

    # Background task: poll EventBus -> forward events to WebSocket
    last_seen_event_id = latest_event_id

    async def forward_events():
        nonlocal last_seen_event_id
        while True:
            if event_bus:
                events = event_bus.replay(str(session_id), last_seen_event_id)
                for ev in events:
                    await websocket.send_json({
                        "type": ev.type.value,
                        "session_id": ev.session_id,
                        "step_id": ev.step_id,
                        "data": ev.data,
                    })
                    last_seen_event_id = ev.event_id
            await asyncio.sleep(0.05)  # 50ms poll

    event_task = asyncio.create_task(forward_events())

    try:
        while True:
            raw = await websocket.receive_text()
            import sys
            sys.stderr.write(f"[WS DEBUG] Received message: {raw[:200]}\n")
            sys.stderr.flush()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                message = {"type": "chat.message", "content": raw}

            msg_type = message.get("type", "chat.message")
            sys.stderr.write(f"[WS DEBUG] Message type: {msg_type}, content length: {len(message.get('content', ''))}\n")
            sys.stderr.flush()

            if msg_type == "chat.message":
                content = message.get("content", "")
                explicit_tool = message.get("tool")

                # DEBUG: 写入文件
                with open("/app/ws_debug.txt", "a") as f:
                    f.write(f"\n=== Received chat.message ===\n")
                    f.write(f"Content: {content}\n")
                    f.write(f"Session: {session_id}\n")

                if not content.strip():
                    continue

                # Persist student message
                with SessionLocal() as db:
                    add_message(db, session_id=session_id, role="student", content=content)

                    # Load conversation history (excluding the one just added)
                    history_msgs = list_messages(db, session_id=session_id, user_id=user_id)
                    api_history = convert_history_to_api(history_msgs[:-1])

                # Execute ReAct loop
                with SessionLocal() as db:
                    await runtime.run_turn(
                        session_id=str(session_id),
                        user_id=user_id,
                        messages=api_history,
                        current_message=content,
                        db=db,
                        explicit_tool=explicit_tool,
                    )

            elif msg_type == "action.cancel":
                await websocket.send_json({
                    "type": "plan.interrupt_request",
                    "session_id": str(session_id),
                    "data": {"reason": "cancel requested"},
                })

    except WebSocketDisconnect:
        event_task.cancel()
    except Exception:
        event_task.cancel()
        raise
