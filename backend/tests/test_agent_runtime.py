"""Unit tests for ToolExecutionTracker, classify_intent, and AgentRuntime.

Behaviour-focused, using mocks to isolate dependencies.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.kernel.agent.events import AgentEvent, EventBus, EventType
from app.kernel.agent.runtime import (
    MAX_TOOL_CALLS_PER_TURN,
    AgentRuntime,
    AgentStep,
    ToolExecutionTracker,
    classify_intent,
)
from app.kernel.agent.tools import SideEffect, ToolRegistry, ToolSpec
from app.kernel.llm import StreamEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockLLM:
    """Mock LLM that yields pre-configured StreamEvent sequences."""

    def __init__(self, events: list[StreamEvent]) -> None:
        self._events = events

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ):
        for event in self._events:
            yield event


class MockLLMPerCall:
    """Mock LLM that yields different events on each successive stream_chat call."""

    def __init__(self, events_per_call: list[list[StreamEvent]]) -> None:
        self._events_per_call = events_per_call
        self._call_index = 0

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ):
        idx = min(self._call_index, len(self._events_per_call) - 1)
        self._call_index += 1
        for event in self._events_per_call[idx]:
            yield event


class RecordingEventBus:
    """EventBus stand-in that records emitted events in memory."""

    def __init__(self) -> None:
        self.emitted: list[AgentEvent] = []

    def emit(self, event: AgentEvent) -> None:
        self.emitted.append(event)

    def replay(self, session_id: str, since_event_id: str | None = None) -> list[AgentEvent]:
        return [e for e in self.emitted if e.session_id == session_id]


class InMemoryRedisClient:
    """Minimal Redis stand-in backed by a plain dict of lists."""

    def __init__(self) -> None:
        self._store: dict[str, list[str]] = {}

    def rpush(self, key: str, value: str) -> None:
        self._store.setdefault(key, []).append(value)

    def lrange(self, key: str, start: int, stop: int) -> list[str]:
        return self._store.get(key, [])[start : stop if stop != -1 else None]

    def expire(self, key: str, ttl: int) -> None:
        pass

    def lindex(self, key: str, index: int) -> str | None:
        data = self._store.get(key, [])
        if not data:
            return None
        return data[index]


def _async_handler(result: Any = None, *, error: Exception | None = None):
    """Return an async callable suitable as a ToolSpec.handler."""

    async def handler(**kwargs: Any) -> Any:
        if error is not None:
            raise error
        return result

    return handler


def _make_tool_registry(tools: dict[str, ToolSpec] | None = None) -> ToolRegistry:
    """Build a ToolRegistry, optionally pre-populated with tools."""
    registry = ToolRegistry()
    for tool in (tools or {}).values():
        registry.register(tool)
    return registry


def _make_tool(name: str = "Test::Tool", result: Any = None, schema: dict | None = None) -> ToolSpec:
    """Build a minimal ToolSpec."""
    return ToolSpec(
        name=name,
        description="测试工具",
        short_intent="执行测试",
        side_effect=SideEffect.READ,
        requires_confirmation=False,
        handler=_async_handler(result=result),
        schema=schema,
    )


# ===================================================================
# ToolExecutionTracker
# ===================================================================


def test_tracker_sig_deterministic() -> None:
    """Same inputs produce the same signature."""
    tracker = ToolExecutionTracker()
    sig1 = tracker.sig("MyTool", {"a": 1, "b": 2})
    sig2 = tracker.sig("MyTool", {"b": 2, "a": 1})  # different key order
    sig3 = tracker.sig("MyTool", {"a": 1, "b": 2})

    assert sig1 == sig2 == sig3
    assert isinstance(sig1, str) and len(sig1) > 0


def test_tracker_already_executed() -> None:
    """After recording, already_executed returns True."""
    tracker = ToolExecutionTracker()
    tracker.record("Grading::Grade", {"file": "hw.pdf"}, {"score": 95}, ok=True)

    assert tracker.already_executed("Grading::Grade", {"file": "hw.pdf"}) is True


def test_tracker_not_executed() -> None:
    """Before recording, already_executed returns False."""
    tracker = ToolExecutionTracker()

    assert tracker.already_executed("Grading::Grade", {"file": "hw.pdf"}) is False


def test_tracker_missed_calls() -> None:
    """missed_calls returns tool calls that have not been executed."""
    tracker = ToolExecutionTracker()
    tracker.record("Grading::Grade", {"file": "hw.pdf"}, {"score": 95}, ok=True)

    llm_calls = [
        {"name": "Grading::Grade", "arguments": {"file": "hw.pdf"}},  # executed
        {"name": "Notes::Save", "arguments": {"text": "note1"}},  # not executed
    ]

    missed = tracker.missed_calls(llm_calls)

    assert len(missed) == 1
    assert missed[0]["name"] == "Notes::Save"


def test_tracker_summary_for_prompt() -> None:
    """summary_for_prompt produces a readable summary of executed tools."""
    tracker = ToolExecutionTracker()
    tracker.record("Grading::Grade", {"file": "hw.pdf"}, {"score": 95}, ok=True)
    tracker.record("Notes::Save", {"text": "hi"}, None, ok=False)

    summary = tracker.summary_for_prompt()

    assert "已执行的工具" in summary
    assert "Grading::Grade" in summary
    assert "成功" in summary
    assert "Notes::Save" in summary
    assert "失败" in summary


def test_tracker_empty_summary() -> None:
    """summary_for_prompt returns empty string when no records exist."""
    tracker = ToolExecutionTracker()

    assert tracker.summary_for_prompt() == ""


# ===================================================================
# classify_intent
# ===================================================================


def test_classify_chitchat() -> None:
    """Simple greetings are classified as chitchat."""
    assert classify_intent("你好") == "chitchat"
    assert classify_intent("谢谢老师") == "chitchat"
    assert classify_intent("hello world") == "chitchat"


def test_classify_tool_hint() -> None:
    """Messages containing tool-related keywords are classified as tool_hint."""
    assert classify_intent("帮我批改这份作业") == "tool_hint"
    assert classify_intent("请上传文件") == "tool_hint"
    assert classify_intent("查看错题本") == "tool_hint"


def test_classify_ambiguous() -> None:
    """Messages that are neither chitchat nor tool_hint are ambiguous."""
    assert classify_intent("这道题怎么做") == "ambiguous"
    assert classify_intent("勾股定理是什么") == "ambiguous"


# ===================================================================
# AgentRuntime
# ===================================================================


def test_runtime_initialize() -> None:
    """After initialize(), _llm, _tool_registry, and _event_bus are non-None."""
    runtime = AgentRuntime()
    llm = MockLLM([])
    registry = _make_tool_registry()
    redis = InMemoryRedisClient()
    event_bus = EventBus(redis)

    runtime.initialize(llm, registry, event_bus)

    assert runtime._llm is not None
    assert runtime._tool_registry is not None
    assert runtime._event_bus is not None


def test_compile_linear_workflow_preserved() -> None:
    """compile_linear_workflow still works: builds a runnable LangGraph graph."""
    runtime = AgentRuntime()
    runtime.initialize(
        llm=MockLLM([]),
        tool_registry=_make_tool_registry(),
        event_bus=EventBus(InMemoryRedisClient()),
    )

    executed_steps: list[str] = []

    async def step_a(state: dict) -> dict:
        executed_steps.append("a")
        return state

    async def step_b(state: dict) -> dict:
        executed_steps.append("b")
        return state

    graph = runtime.compile_linear_workflow(
        dict,
        [AgentStep(name="a", handler=step_a), AgentStep(name="b", handler=step_b)],
    )

    result = asyncio.run(graph.ainvoke({"value": 42}))
    assert executed_steps == ["a", "b"]
    assert result["value"] == 42


def test_compile_empty_steps_raises() -> None:
    """compile_linear_workflow raises ValueError when given no steps."""
    runtime = AgentRuntime()
    runtime.initialize(
        llm=MockLLM([]),
        tool_registry=_make_tool_registry(),
        event_bus=EventBus(InMemoryRedisClient()),
    )

    with pytest.raises(ValueError, match="at least one step"):
        runtime.compile_linear_workflow(dict, [])


def test_build_tool_schemas() -> None:
    """_build_tool_schemas converts ToolSpecs to Responses API format."""
    runtime = AgentRuntime()
    tool = _make_tool(
        name="Grading::Grade",
        result=None,
        schema={"type": "object", "properties": {"file": {"type": "string"}}, "required": ["file"]},
    )
    registry = _make_tool_registry({"Grading::Grade": tool})
    runtime.initialize(
        llm=MockLLM([]),
        tool_registry=registry,
        event_bus=EventBus(InMemoryRedisClient()),
    )

    schemas = runtime._build_tool_schemas(registry.list_all())

    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["type"] == "function"
    assert schema["name"] == "Grading::Grade"
    assert schema["description"] == "测试工具"
    assert schema["strict"] is True
    assert schema["parameters"]["properties"]["file"]["type"] == "string"


def test_run_turn_chitchat() -> None:
    """Chitchat messages take the fast path (no tool schemas passed to LLM)."""
    llm = MockLLM([StreamEvent(type="text_delta", delta="你好同学！"), StreamEvent(type="done")])
    registry = _make_tool_registry()
    redis = InMemoryRedisClient()
    event_bus = EventBus(redis)
    runtime = AgentRuntime()
    runtime.initialize(llm, registry, event_bus)

    # Mock the db and context dependencies
    import unittest.mock as mock

    fake_user = mock.MagicMock()
    fake_user.grade = 5
    fake_user.main_subject = "数学"

    fake_db = mock.MagicMock()
    fake_db.get.return_value = fake_user

    with mock.patch("app.kernel.agent.context.load_identity", return_value={"name": "test"}), \
         mock.patch("app.kernel.agent.context.build_system_prompt", return_value="sys"), \
         mock.patch("app.kernel.agent.context.assemble_messages", return_value=[{"role": "user", "content": "你好"}]), \
         mock.patch("app.kernel.chat.service.add_message"):
        reply = asyncio.run(
            runtime.run_turn(
                session_id="1",
                user_id=1,
                messages=[],
                current_message="你好",
                db=fake_db,
            )
        )

    assert reply == "你好同学！"

    # Verify CHAT_TEXT_DELTA events were emitted
    events = event_bus.replay("1")
    delta_events = [e for e in events if e.type == EventType.CHAT_TEXT_DELTA]
    assert len(delta_events) == 1
    assert delta_events[0].data["delta"] == "你好同学！"


def test_run_turn_with_tool_call() -> None:
    """Tool call scenario: LLM emits tool_call, runtime executes it and feeds result back."""
    tool = _make_tool(name="Grading::Grade", result={"score": 95})
    registry = _make_tool_registry({"Grading::Grade": tool})

    llm = MockLLM([
        StreamEvent(type="text_delta", delta="正在批改"),
        StreamEvent(
            type="tool_call",
            tool_name="Grading::Grade",
            tool_args={"file": "hw.pdf"},
            tool_call_id="call-1",
        ),
        StreamEvent(type="text_delta", delta="，批改完成！"),
        StreamEvent(type="done"),
    ])
    redis = InMemoryRedisClient()
    event_bus = EventBus(redis)
    runtime = AgentRuntime()
    runtime.initialize(llm, registry, event_bus)

    import unittest.mock as mock

    fake_user = mock.MagicMock()
    fake_user.grade = 5
    fake_user.main_subject = "数学"

    fake_db = mock.MagicMock()
    fake_db.get.return_value = fake_user

    with mock.patch("app.kernel.agent.context.load_identity", return_value={"name": "test"}), \
         mock.patch("app.kernel.agent.context.build_system_prompt", return_value="sys"), \
         mock.patch("app.kernel.agent.context.assemble_messages", return_value=[{"role": "user", "content": "批改作业"}]), \
         mock.patch("app.kernel.chat.service.add_message"):
        reply = asyncio.run(
            runtime.run_turn(
                session_id="1",
                user_id=1,
                messages=[],
                current_message="帮我批改这份作业",
                db=fake_db,
            )
        )

    assert "正在批改" in reply
    assert "批改完成" in reply

    # Verify tool-related events were emitted
    events = event_bus.replay("1")
    tool_call_events = [e for e in events if e.type == EventType.PLAN_STEP_TOOL_CALL]
    assert len(tool_call_events) >= 1
    assert tool_call_events[0].data["tool_name"] == "Grading::Grade"

    tool_result_events = [e for e in events if e.type == EventType.PLAN_STEP_TOOL_RESULT]
    assert len(tool_result_events) >= 1
    assert tool_result_events[0].data["result"] == {"score": 95}

    # PLAN_DONE should be emitted at the end
    plan_done_events = [e for e in events if e.type == EventType.PLAN_DONE]
    assert len(plan_done_events) == 1


def test_run_turn_max_rounds() -> None:
    """Runtime stops after MAX_TOOL_CALLS_PER_TURN rounds of tool calls."""
    tool = _make_tool(name="Test::Tool", result={"ok": True})
    registry = _make_tool_registry({"Test::Tool": tool})

    # Each round: LLM emits a tool_call + text_delta, then done.
    # Each round has different args so the tracker doesn't deduplicate.
    # The last call (index MAX_TOOL_CALLS_PER_TURN) emits only text + done (no tool),
    # which breaks the loop naturally.
    def _make_tool_round(i: int) -> list[StreamEvent]:
        return [
            StreamEvent(
                type="tool_call",
                tool_name="Test::Tool",
                tool_args={"round": i},
                tool_call_id=f"call-{i}",
            ),
            StreamEvent(type="text_delta", delta=f"processing{i}"),
            StreamEvent(type="done"),
        ]

    final_round = [
        StreamEvent(type="text_delta", delta="done"),
        StreamEvent(type="done"),
    ]

    # First MAX_TOOL_CALLS_PER_TURN calls emit tool_calls, last call emits only text
    events_per_call = [_make_tool_round(i) for i in range(MAX_TOOL_CALLS_PER_TURN)] + [final_round]

    llm = MockLLMPerCall(events_per_call)
    redis = InMemoryRedisClient()
    event_bus = EventBus(redis)
    runtime = AgentRuntime()
    runtime.initialize(llm, registry, event_bus)

    import unittest.mock as mock

    fake_user = mock.MagicMock()
    fake_user.grade = 5
    fake_user.main_subject = "数学"

    fake_db = mock.MagicMock()
    fake_db.get.return_value = fake_user

    with mock.patch("app.kernel.agent.context.load_identity", return_value={"name": "test"}), \
         mock.patch("app.kernel.agent.context.build_system_prompt", return_value="sys"), \
         mock.patch("app.kernel.agent.context.assemble_messages", return_value=[{"role": "user", "content": "test"}]), \
         mock.patch("app.kernel.chat.service.add_message"):
        reply = asyncio.run(
            runtime.run_turn(
                session_id="1",
                user_id=1,
                messages=[],
                current_message="反复调用工具",
                db=fake_db,
            )
        )

    # The runtime executed exactly MAX_TOOL_CALLS_PER_TURN tool-call rounds
    all_events = event_bus.replay("1")
    tool_call_events = [e for e in all_events if e.type == EventType.PLAN_STEP_TOOL_CALL]
    assert len(tool_call_events) == MAX_TOOL_CALLS_PER_TURN

    # PLAN_DONE should still be emitted
    plan_done_events = [e for e in all_events if e.type == EventType.PLAN_DONE]
    assert len(plan_done_events) == 1
