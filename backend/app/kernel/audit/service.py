from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.models import AuditLog, User


SENSITIVE_KEY_PARTS = ("password", "token", "secret", "authorization", "api_key", "apikey")


class AuditLogger:
    """Kernel-owned audit logger.

    Callers add events to the current database transaction. Use `commit=True`
    only for standalone security events such as failed login attempts.
    """

    def record(
        self,
        db: Session,
        *,
        event_type: str,
        actor: User | None = None,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
        outcome: str = "success",
        resource_type: str | None = None,
        resource_id: str | int | None = None,
        summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
        request: Request | None = None,
        commit: bool = False,
    ) -> AuditLog:
        event = AuditLog(
            event_type=event_type[:80],
            outcome=outcome[:16],
            actor_user_id=actor.id if actor else actor_user_id,
            actor_username=(actor.username if actor else actor_username),
            resource_type=resource_type[:64] if resource_type else None,
            resource_id=str(resource_id)[:64] if resource_id is not None else None,
            summary=summary[:255] if summary else None,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
            event_metadata=_redact(metadata or {}),
            error_message=error_message[:1000] if error_message else None,
        )
        db.add(event)
        if commit:
            db.commit()
            db.refresh(event)
        return event

    def list_for_user(self, db: Session, user_id: int, *, limit: int = 50, event_type: str | None = None) -> list[AuditLog]:
        query = (
            select(AuditLog)
            .where(AuditLog.actor_user_id == user_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(min(max(limit, 1), 100))
        )
        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        return list(db.scalars(query).all())

    def list_all(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
        actor_username: str | None = None,
    ) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        if actor_username:
            query = query.where(AuditLog.actor_username == actor_username)
        query = query.offset(max(offset, 0)).limit(min(max(limit, 1), 10_000))
        return list(db.scalars(query).all())


def serialize_audit_log(event: AuditLog) -> dict[str, Any]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "outcome": event.outcome,
        "actor_user_id": event.actor_user_id,
        "actor_username": event.actor_username,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "summary": event.summary,
        "metadata": event.event_metadata or {},
        "error_message": event.error_message,
        "created_at": event.created_at,
    }


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host[:64]


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    user_agent = request.headers.get("user-agent")
    return user_agent[:255] if user_agent else None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if _is_sensitive_key(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
