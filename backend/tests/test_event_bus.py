"""Unit tests for EventBus and AgentEvent (behaviour-focused, no real Redis)."""

from __future__ import annotations

import json

import pytest

from app.kernel.agent.events import AgentEvent, EventType, EventBus
from app.kernel.redis import InMemoryRedisClient


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def redis() -> InMemoryRedisClient:
    return InMemoryRedisClient()


@pytest.fixture()
def bus(redis: InMemoryRedisClient) -> EventBus:
    return EventBus(redis)


def _make_event(
    session_id: str = "s1",
    step_id: str | None = None,
    data: dict | None = None,
    **kwargs,
) -> AgentEvent:
    """Helper to create an AgentEvent with sensible defaults."""
    return AgentEvent(
        type=EventType.CHAT_TEXT_DELTA,
        session_id=session_id,
        step_id=step_id,
        data=data or {},
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. emit and replay single event
# ---------------------------------------------------------------------------

def test_emit_and_replay_single_event(bus: EventBus) -> None:
    """An emitted event can be replayed from the same session."""
    event = _make_event(session_id="s1", data={"text": "hello"})

    bus.emit(event)

    replayed = bus.replay("s1")
    assert len(replayed) == 1
    assert replayed[0].session_id == "s1"
    assert replayed[0].data == {"text": "hello"}
    assert replayed[0].event_id == event.event_id


# ---------------------------------------------------------------------------
# 2. emit multiple events preserves ordering
# ---------------------------------------------------------------------------

def test_emit_multiple_events_ordering(bus: EventBus) -> None:
    """Events are replayed in the same order they were emitted."""
    ev1 = _make_event(session_id="s1", data={"seq": 1})
    ev2 = _make_event(session_id="s1", data={"seq": 2})
    ev3 = _make_event(session_id="s1", data={"seq": 3})

    bus.emit(ev1)
    bus.emit(ev2)
    bus.emit(ev3)

    replayed = bus.replay("s1")
    assert [e.data["seq"] for e in replayed] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 3. replay on empty session
# ---------------------------------------------------------------------------

def test_replay_empty_session(bus: EventBus) -> None:
    """Replaying a session with no events returns an empty list."""
    assert bus.replay("nonexistent") == []


# ---------------------------------------------------------------------------
# 4. replay with since_event_id
# ---------------------------------------------------------------------------

def test_replay_since_event_id(bus: EventBus) -> None:
    """since_event_id skips all events up to and including the given id."""
    ev1 = _make_event(session_id="s1", data={"seq": 1})
    ev2 = _make_event(session_id="s1", data={"seq": 2})
    ev3 = _make_event(session_id="s1", data={"seq": 3})

    bus.emit(ev1)
    bus.emit(ev2)
    bus.emit(ev3)

    replayed = bus.replay("s1", since_event_id=ev2.event_id)
    assert len(replayed) == 1
    assert replayed[0].event_id == ev3.event_id


# ---------------------------------------------------------------------------
# 5. replay with non-existent since_event_id returns all
# ---------------------------------------------------------------------------

def test_replay_since_nonexistent_id(bus: EventBus) -> None:
    """When since_event_id is not found, all events are returned."""
    ev1 = _make_event(session_id="s1", data={"seq": 1})
    bus.emit(ev1)

    replayed = bus.replay("s1", since_event_id="does_not_exist")
    assert len(replayed) == 1
    assert replayed[0].event_id == ev1.event_id


# ---------------------------------------------------------------------------
# 6. get_latest_event_id on empty session
# ---------------------------------------------------------------------------

def test_get_latest_event_id_empty(bus: EventBus) -> None:
    """An empty session has no latest event id."""
    assert bus.get_latest_event_id("s1") is None


# ---------------------------------------------------------------------------
# 7. get_latest_event_id after emit
# ---------------------------------------------------------------------------

def test_get_latest_event_id_after_emit(bus: EventBus) -> None:
    """After emitting events, latest event id matches the last emitted event."""
    ev1 = _make_event(session_id="s1")
    ev2 = _make_event(session_id="s1")

    bus.emit(ev1)
    bus.emit(ev2)

    assert bus.get_latest_event_id("s1") == ev2.event_id


# ---------------------------------------------------------------------------
# 8. AgentEvent serialisation roundtrip
# ---------------------------------------------------------------------------

def test_event_serialization_roundtrip() -> None:
    """to_json -> from_json preserves all fields."""
    original = AgentEvent(
        type=EventType.PLAN_STEP_TOOL_CALL,
        session_id="sess-abc",
        step_id="step-1",
        data={"tool": "search", "query": "pytest"},
        event_id="fixedid123",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    restored = AgentEvent.from_json(original.to_json())

    assert restored.type == original.type
    assert restored.session_id == original.session_id
    assert restored.step_id == original.step_id
    assert restored.data == original.data
    assert restored.event_id == original.event_id
    assert restored.timestamp == original.timestamp


# ---------------------------------------------------------------------------
# 9. EventType enum has all 12 members
# ---------------------------------------------------------------------------

def test_event_types_all_present() -> None:
    """EventType exposes exactly the 12 event types defined in ADR-0013."""
    expected = {
        "session.welcome",
        "plan.start",
        "plan.step.started",
        "plan.step.tool_call",
        "plan.step.tool_result",
        "plan.step.error",
        "plan.step.done",
        "plan.done",
        "plan.interrupt_request",
        "chat.text.delta",
        "memory.recorded",
        "session.end",
    }
    actual = {e.value for e in EventType}
    assert actual == expected
    assert len(EventType) == 12


# ---------------------------------------------------------------------------
# 10. different sessions are isolated
# ---------------------------------------------------------------------------

def test_emit_different_sessions_isolated(bus: EventBus) -> None:
    """Events in one session are invisible when replaying another session."""
    ev_a = _make_event(session_id="alpha", data={"from": "alpha"})
    ev_b = _make_event(session_id="beta", data={"from": "beta"})

    bus.emit(ev_a)
    bus.emit(ev_b)

    assert len(bus.replay("alpha")) == 1
    assert bus.replay("alpha")[0].data["from"] == "alpha"
    assert len(bus.replay("beta")) == 1
    assert bus.replay("beta")[0].data["from"] == "beta"


# ---------------------------------------------------------------------------
# 11. event has a timestamp
# ---------------------------------------------------------------------------

def test_agent_event_has_timestamp() -> None:
    """An AgentEvent created with defaults carries a non-empty timestamp string."""
    event = _make_event()
    assert event.timestamp  # truthy, non-empty string
    # ISO format sanity: contains 'T' separator
    assert "T" in event.timestamp


# ---------------------------------------------------------------------------
# 12. event has a unique id
# ---------------------------------------------------------------------------

def test_agent_event_has_unique_id() -> None:
    """Two separately created AgentEvents have distinct event_id values."""
    ev1 = _make_event()
    ev2 = _make_event()
    assert ev1.event_id != ev2.event_id
    # default id is 16 hex chars
    assert len(ev1.event_id) == 16
