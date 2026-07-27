from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.plugins.agent_chat.models import ChatMessage, ChatSession


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:24]}"


# ── 会话 CRUD ─────────────────────────────────────

def create_session(db: Session, user_id: int, title: str | None = None) -> ChatSession:
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title=title or "新会话",
        last_active_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, user_id: int) -> list[ChatSession]:
    return list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.last_active_at.desc())
        ).all()
    )


def get_session(db: Session, session_id: str, user_id: int) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    if session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该会话")
    return session


def update_session(db: Session, session_id: str, user_id: int, title: str | None = None) -> ChatSession:
    session = get_session(db, session_id, user_id)
    if title is not None:
        session.title = title
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: str, user_id: int) -> None:
    session = get_session(db, session_id, user_id)
    db.delete(session)
    db.commit()


# ── 消息 CRUD ─────────────────────────────────────

def add_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    *,
    card_type: str | None = None,
    card_payload: dict | None = None,
    step_id: str | None = None,
) -> ChatMessage:
    message = ChatMessage(
        id=_new_id("msg_"),
        session_id=session_id,
        role=role,
        content=content,
        card_type=card_type,
        card_payload=card_payload,
        step_id=step_id,
    )
    db.add(message)
    # 更新会话的 last_active_at
    db.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(last_active_at=datetime.now(UTC))
    )
    db.commit()
    db.refresh(message)
    return message


def list_messages(db: Session, session_id: str, user_id: int, limit: int = 100) -> list[ChatMessage]:
    get_session(db, session_id, user_id)  # 校验归属
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(min(limit, 500))
        ).all()
    )


def get_messages_since(db: Session, session_id: str, user_id: int, since_step_id: str) -> list[ChatMessage]:
    """断线回放：返回 since_step_id 之后的消息。"""
    get_session(db, session_id, user_id)  # 校验归属
    # 先找到 since_step_id 对应消息的时间
    anchor = db.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.step_id == since_step_id,
        )
    )
    if anchor is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的 step_id")
    return list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.created_at > anchor.created_at,
            )
            .order_by(ChatMessage.created_at.asc())
        ).all()
    )


def update_message_card(
    db: Session, message_id: str, card_type: str, card_payload: dict
) -> ChatMessage:
    """更新消息的卡片内容（用于批改中→批改完成的替换）。"""
    message = db.get(ChatMessage, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    message.card_type = card_type
    message.card_payload = card_payload
    db.commit()
    db.refresh(message)
    return message
