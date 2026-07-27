"""WebSocket event emitter — 13 event types for the Agent chat protocol."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _step_id() -> str:
    return f"step_{uuid.uuid4().hex[:16]}"


# ── 序列化 ────────────────────────────────────────

async def send_event(ws: WebSocket, event: str, data: dict[str, Any], *, step_id: str | None = None, session_id: str = "") -> str:
    """Send a structured event to a WebSocket client. Returns the step_id used."""
    sid = step_id or _step_id()
    payload = {
        "event": event,
        "step_id": sid,
        "timestamp": _now_iso(),
        "session_id": session_id,
        "data": data,
    }
    await ws.send_text(json.dumps(payload, ensure_ascii=False))
    return sid


# ── 13 类事件 ─────────────────────────────────────

async def emit_session_welcome(ws: WebSocket, session_id: str, *, replay_from_step_id: str | None, session_title: str) -> None:
    await ws.send_text(json.dumps({
        "event": "session.welcome",
        "timestamp": _now_iso(),
        "session_id": session_id,
        "data": {
            "replay_from_step_id": replay_from_step_id,
            "session_title": session_title,
        },
    }, ensure_ascii=False))


async def emit_plan_start(ws: WebSocket, session_id: str, plan_id: str, goal: str) -> str:
    return await send_event(ws, "plan.start", {"plan_id": plan_id, "goal": goal}, session_id=session_id)


async def emit_intent_recognized(
    ws: WebSocket, session_id: str, *,
    intent: str, confidence: float, description: str,
    has_file: bool, tool_to_call: str | None,
) -> str:
    return await send_event(ws, "intent.recognized", {
        "intent": intent,
        "confidence": confidence,
        "description": description,
        "has_file": has_file,
        "tool_to_call": tool_to_call,
    }, session_id=session_id)


async def emit_tool_call(
    ws: WebSocket, session_id: str, *,
    tool_address: str, proposal: str,
    source: str = "agent", side_effect: str = "read",
) -> str:
    return await send_event(ws, "plan.step.tool_call", {
        "tool_address": tool_address,
        "proposal": proposal,
        "source": source,
        "side_effect": side_effect,
    }, session_id=session_id)


async def emit_step_started(ws: WebSocket, session_id: str, tool_address: str) -> str:
    return await send_event(ws, "plan.step.started", {"tool_address": tool_address}, session_id=session_id)


async def emit_tool_result(
    ws: WebSocket, session_id: str, *,
    tool_address: str, success: bool,
    card_type: str | None = None, card_payload: dict | None = None,
    summary: str = "",
) -> str:
    return await send_event(ws, "plan.step.tool_result", {
        "tool_address": tool_address,
        "success": success,
        "card_type": card_type,
        "card_payload": card_payload,
        "summary": summary,
    }, session_id=session_id)


async def emit_step_error(
    ws: WebSocket, session_id: str, *,
    tool_address: str, error_message: str,
    card_type: str | None = None, card_payload: dict | None = None,
) -> str:
    return await send_event(ws, "plan.step.error", {
        "tool_address": tool_address,
        "error_message": error_message,
        "card_type": card_type,
        "card_payload": card_payload,
    }, session_id=session_id)


async def emit_step_done(ws: WebSocket, session_id: str, tool_address: str) -> str:
    return await send_event(ws, "plan.step.done", {"tool_address": tool_address}, session_id=session_id)


async def emit_text_delta(ws: WebSocket, session_id: str, *, delta: str, accumulated: str) -> str:
    return await send_event(ws, "chat.text.delta", {
        "delta": delta,
        "accumulated": accumulated,
    }, session_id=session_id)


async def emit_plan_done(ws: WebSocket, session_id: str, plan_id: str, *, success: bool, summary: str) -> str:
    return await send_event(ws, "plan.done", {
        "plan_id": plan_id,
        "success": success,
        "summary": summary,
    }, session_id=session_id)


async def emit_interrupt_request(ws: WebSocket, session_id: str, plan_id: str, reason: str = "student_requested") -> str:
    return await send_event(ws, "plan.interrupt_request", {
        "plan_id": plan_id,
        "reason": reason,
    }, session_id=session_id)


async def emit_memory_recorded(ws: WebSocket, session_id: str, memory_type: str, summary: str) -> str:
    return await send_event(ws, "memory.recorded", {
        "memory_type": memory_type,
        "summary": summary,
    }, session_id=session_id)


async def emit_session_end(ws: WebSocket, session_id: str, reason: str = "completed") -> str:
    return await send_event(ws, "session.end", {"reason": reason}, session_id=session_id)
