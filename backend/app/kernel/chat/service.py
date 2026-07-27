"""Chat session and message service — kernel-owned persistence layer."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.kernel.models import ChatMessage, ChatSession


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def create_session(db: Session, *, user_id: int, title: str = "新对话") -> ChatSession:
    """创建新的聊天会话"""
    session = ChatSession(
        user_id=user_id,
        title=title[:128],
        last_active_at=datetime.now(UTC),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(db: Session, *, user_id: int) -> list[ChatSession]:
    """列出用户的所有会话，按最近活跃排序"""
    return list(
        db.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.last_active_at.desc())
        ).all()
    )


def get_session(db: Session, *, session_id: int, user_id: int) -> ChatSession | None:
    """获取单个会话（带权限检查）"""
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def rename_session(
    db: Session, *, session_id: int, user_id: int, title: str
) -> ChatSession | None:
    """重命名会话"""
    session = get_session(db, session_id=session_id, user_id=user_id)
    if session is None:
        return None
    session.title = title[:128]
    session.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, *, session_id: int, user_id: int) -> bool:
    """删除会话及其所有消息"""
    session = get_session(db, session_id=session_id, user_id=user_id)
    if session is None:
        return False
    # 先删消息
    messages = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
    ).all()
    for msg in messages:
        db.delete(msg)
    db.delete(session)
    db.commit()
    return True


def touch_session(db: Session, *, session_id: int) -> None:
    """更新会话的最后活跃时间"""
    session = db.get(ChatSession, session_id)
    if session:
        session.last_active_at = datetime.now(UTC)
        db.flush()


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------

def add_message(
    db: Session,
    *,
    session_id: int,
    role: str,
    content: str = "",
    card_type: str | None = None,
    card_payload: dict[str, Any] | None = None,
    step_id: str | None = None,
) -> ChatMessage:
    """添加一条消息到会话"""
    if role not in ("student", "agent", "system"):
        raise ValueError(f"Invalid role: {role}")
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        card_type=card_type,
        card_payload=card_payload,
        step_id=step_id,
    )
    db.add(msg)
    touch_session(db, session_id=session_id)
    db.commit()
    db.refresh(msg)
    return msg


def list_messages(
    db: Session,
    *,
    session_id: int,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[ChatMessage]:
    """列出会话的消息（带权限检查）"""
    # 先验证会话属于该用户
    session = get_session(db, session_id=session_id, user_id=user_id)
    if session is None:
        return []
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 200))
        ).all()
    )


def get_message_count(db: Session, *, session_id: int) -> int:
    """获取会话的消息数量"""
    return db.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.session_id == session_id)
    ) or 0


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def serialize_session(session: ChatSession) -> dict[str, Any]:
    """序列化会话为 API 响应格式"""
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
    }


def serialize_message(msg: ChatMessage) -> dict[str, Any]:
    """序列化消息为 API 响应格式"""
    return {
        "id": msg.id,
        "session_id": msg.session_id,
        "role": msg.role,
        "content": msg.content,
        "card_type": msg.card_type,
        "card_payload": msg.card_payload,
        "step_id": msg.step_id,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
