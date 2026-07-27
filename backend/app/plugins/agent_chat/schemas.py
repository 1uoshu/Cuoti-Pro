from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 会话 ──────────────────────────────────────────

class SessionCreate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=128)


class SessionPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=128)


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime

    model_config = {"from_attributes": True}


# ── 消息 ──────────────────────────────────────────

class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    card_type: Optional[str] = None
    card_payload: Optional[dict] = None
    step_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TextMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


# ── 待复核确认 ────────────────────────────────────

class ReviewConfirmRequest(BaseModel):
    question_ids: list[int] = Field(..., min_length=1)


# ── 统一消息入口 ──────────────────────────────────

class UnifiedMessageOut(BaseModel):
    message_id: str
    session_id: str
    has_file: bool
    assignment_id: Optional[int] = None
    task_id: Optional[str] = None


# ── 回放 ──────────────────────────────────────────

class ReplayOut(BaseModel):
    replay_from: str
    messages: list[MessageOut]
    pending_events: list[dict]
