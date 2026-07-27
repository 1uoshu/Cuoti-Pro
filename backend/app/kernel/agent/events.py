"""Event bus for Agent runtime — Redis list-backed with replay support."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """12 类 WebSocket 事件，ADR 0013 定义。"""

    SESSION_WELCOME = "session.welcome"
    PLAN_START = "plan.start"
    PLAN_STEP_STARTED = "plan.step.started"
    PLAN_STEP_TOOL_CALL = "plan.step.tool_call"
    PLAN_STEP_TOOL_RESULT = "plan.step.tool_result"
    PLAN_STEP_ERROR = "plan.step.error"
    PLAN_STEP_DONE = "plan.step.done"
    PLAN_DONE = "plan.done"
    PLAN_INTERRUPT_REQUEST = "plan.interrupt_request"
    CHAT_TEXT_DELTA = "chat.text.delta"
    MEMORY_RECORDED = "memory.recorded"
    SESSION_END = "session.end"


@dataclass
class AgentEvent:
    """单个 Agent 事件。"""

    type: EventType
    session_id: str
    step_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type.value,
                "session_id": self.session_id,
                "step_id": self.step_id,
                "data": self.data,
                "event_id": self.event_id,
                "timestamp": self.timestamp,
            },
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> AgentEvent:
        d = json.loads(raw)
        return cls(
            type=EventType(d["type"]),
            session_id=d["session_id"],
            step_id=d.get("step_id"),
            data=d.get("data", {}),
            event_id=d.get("event_id", ""),
            timestamp=d.get("timestamp", ""),
        )


class EventBus:
    """Redis list-backed event bus with replay support.

    使用 Redis list 存储事件，因为现有 RedisStore 不支持 XADD/XRANGE。
    用 list 的 RPUSH/LRANGE 模拟事件日志。
    """

    STREAM_PREFIX = "agent:events:"
    STREAM_TTL_SECONDS = 86400  # 24 hours

    def __init__(self, redis: Any) -> None:  # redis: RedisStore
        self._redis = redis

    def _stream_key(self, session_id: str) -> str:
        return f"{self.STREAM_PREFIX}{session_id}"

    def emit(self, event: AgentEvent) -> None:
        """发射一个事件到 Redis。"""
        key = self._stream_key(event.session_id)
        self._redis.rpush(key, event.to_json())
        self._redis.expire(key, self.STREAM_TTL_SECONDS)

    def replay(
        self,
        session_id: str,
        since_event_id: str | None = None,
    ) -> list[AgentEvent]:
        """回放某个 session 的事件，可选从某个 event_id 之后开始。"""
        key = self._stream_key(session_id)
        raw_list = self._redis.lrange(key, 0, -1)
        events = [AgentEvent.from_json(r) for r in raw_list]
        if since_event_id is None:
            return events
        for i, ev in enumerate(events):
            if ev.event_id == since_event_id:
                return events[i + 1 :]
        return events

    def get_latest_event_id(self, session_id: str) -> str | None:
        """获取最近一个事件的 event_id，用于断线重连。"""
        key = self._stream_key(session_id)
        raw = self._redis.lindex(key, -1)
        if raw:
            return AgentEvent.from_json(raw).event_id
        return None
