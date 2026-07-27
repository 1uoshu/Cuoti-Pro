"""Agent runtime -- ReAct loop with ToolExecutionTracker.

借鉴 rust_code_cli 的设计：
- 意图快速分流（省 LLM 调用）
- ToolExecutionTracker（去重 + 补偿）
- TurnEnd 暂缓（工具执行后强制确认）

ADR 0007: Plan-and-Execute with Interrupt
ADR 0008: Main Agent with Sub-Agent Tool Delegation
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from app.kernel.agent.events import AgentEvent, EventBus, EventType

MAX_TOOL_CALLS_PER_TURN = 5


# ── 保留现有接口（插件依赖） ──────────────────────────────────────────


@dataclass(frozen=True)
class AgentStep:
    """A named step inside a linear LangGraph workflow."""

    name: str
    handler: Callable[[Any], Any]


# ── 新增：工具执行追踪器 ─────────────────────────────────


class ToolExecutionTracker:
    """工具执行追踪器 -- 去重 + 补偿。

    借鉴 rust_code_cli 的 ToolExecutionTracker：
    - 用签名（tool_name + args JSON）做去重键
    - 记录已执行工具，注入下一轮 prompt
    - 对比 LLM 输出与已执行记录，补偿遗漏
    """

    def __init__(self) -> None:
        self._executed: dict[str, Any] = {}
        self._records: list[dict[str, Any]] = []

    def sig(self, tool_name: str, args: dict[str, Any]) -> str:
        return f"{tool_name}:{json.dumps(args, sort_keys=True)}"

    def already_executed(self, tool_name: str, args: dict[str, Any]) -> bool:
        return self.sig(tool_name, args) in self._executed

    def record(self, tool_name: str, args: dict[str, Any], result: Any, ok: bool) -> None:
        s = self.sig(tool_name, args)
        self._executed[s] = result
        self._records.append({"tool": tool_name, "ok": ok, "sig": s})

    def missed_calls(self, tool_calls_from_llm: list[dict[str, Any]]) -> list[dict[str, Any]]:
        missed = []
        for tc in tool_calls_from_llm:
            s = self.sig(tc["name"], tc.get("arguments", {}))
            if s not in self._executed:
                missed.append(tc)
        return missed

    def summary_for_prompt(self) -> str:
        if not self._records:
            return ""
        lines = ["已执行的工具:"]
        for r in self._records:
            status = "成功" if r["ok"] else "失败"
            lines.append(f"  - {r['tool']}: {status}")
        return "\n".join(lines)


# ── 新增：意图快速分流 ────────────────────────────────────


def classify_intent(message: str) -> str:
    """规则匹配分流，省一次 LLM 调用。

    返回: "chitchat" | "tool_hint" | "ambiguous"
    """
    chitchat = ["你好", "谢谢", "嗯", "好的", "知道了", "hi", "hello", "thanks"]
    if any(message.strip().startswith(p) for p in chitchat):
        return "chitchat"
    tool_hints = ["批改", "上传", "错题", "归档", "作业"]
    if any(h in message for h in tool_hints):
        return "tool_hint"
    return "ambiguous"


# ── 新增：Agent Runtime ──────────────────────────────────


class AgentRuntime:
    """Kernel-owned Agent runtime -- ReAct 循环。

    借鉴 rust_code_cli 的 stream_kernel_turn 设计：
    1. 意图快速分流
    2. ReAct 循环（最多 5 轮工具调用）
    3. ToolExecutionTracker（去重 + 补偿）
    4. TurnEnd 暂缓（工具执行后强制确认）
    """

    def __init__(self) -> None:
        self._planner: Any = None  # 保留兼容
        self._executor: Any = None  # 保留兼容
        self._event_bus: EventBus | None = None
        self._llm: Any = None
        self._tool_registry: Any = None

    def initialize(self, llm: Any, tool_registry: Any, event_bus: EventBus) -> None:
        """运行时初始化（在 app startup 时调用）"""
        self._llm = llm
        self._tool_registry = tool_registry
        self._event_bus = event_bus

    async def run_turn(
        self,
        session_id: str,
        user_id: int,
        messages: list[dict[str, Any]],
        current_message: str,
        db: Any,
        explicit_tool: str | None = None,
    ) -> str:
        """执行一个学生 turn 的完整 ReAct 循环。

        Args:
            session_id: 会话 ID
            user_id: 用户 ID
            messages: 对话历史（API 格式）
            current_message: 当前学生消息
            db: SQLAlchemy Session
            explicit_tool: 学生显式选择的工具名（Plugin::Tool 格式）

        Returns:
            Agent 的最终文本回复
        """
        from app.kernel.agent.context import (
            assemble_messages,
            build_system_prompt,
            load_identity,
        )
        from app.kernel.chat.service import add_message
        from app.kernel.models import User

        # 1. 加载身份和学生信息
        identity = load_identity("agent")
        tools = self._tool_registry.list_all()
        user = db.get(User, user_id)
        profile = (
            {"grade": user.grade, "main_subject": user.main_subject} if user else None
        )
        system_prompt = build_system_prompt(identity, tools, profile)

        # 2. 意图快速分流（显式工具绑定时跳过）
        intent = classify_intent(current_message) if not explicit_tool else "ambiguous"
        if intent == "chitchat":
            api_messages = assemble_messages(system_prompt, messages, current_message)
            reply = await self._stream_and_collect(api_messages, session_id, tools=None)
            add_message(
                db, session_id=int(session_id), role="agent", content=reply
            )
            return reply

        # 3. ReAct 循环
        api_messages = assemble_messages(system_prompt, messages, current_message)

        # 显式工具绑定：注入约束消息，LLM 必须执行该工具
        if explicit_tool:
            api_messages.append({
                "role": "system",
                "content": (
                    f"学生显式调用了工具「{explicit_tool}」。"
                    f"你必须在本轮中调用此工具，不要跳过或询问学生。"
                    f"从学生的消息中提取参数并执行。"
                ),
            })

        tool_schemas = self._build_tool_schemas(tools)
        tracker = ToolExecutionTracker()
        final_reply = ""

        for round_num in range(MAX_TOOL_CALLS_PER_TURN):
            tool_called_this_round = False
            round_tool_calls: list[dict[str, Any]] = []

            async for event in self._llm.stream_chat(api_messages, tool_schemas):
                if event.type == "text_delta":
                    final_reply += event.delta
                    self._emit(
                        session_id,
                        EventType.CHAT_TEXT_DELTA,
                        data={"delta": event.delta},
                    )

                elif event.type == "tool_call":
                    round_tool_calls.append(
                        {
                            "name": event.tool_name,
                            "arguments": event.tool_args,
                            "call_id": event.tool_call_id,
                        }
                    )
                    if tracker.already_executed(event.tool_name, event.tool_args):
                        continue

                    tool_called_this_round = True
                    self._emit(
                        session_id,
                        EventType.PLAN_STEP_TOOL_CALL,
                        data={"tool_name": event.tool_name, "round": round_num},
                    )

                    tool = self._tool_registry.get(event.tool_name)
                    if tool:
                        try:
                            result = await tool.handler(**event.tool_args)
                            tracker.record(
                                event.tool_name, event.tool_args, result, ok=True
                            )
                            self._emit(
                                session_id,
                                EventType.PLAN_STEP_TOOL_RESULT,
                                data={"result": result},
                            )
                            # Responses API format: function_call item
                            api_messages.append(
                                {
                                    "type": "function_call",
                                    "call_id": event.tool_call_id,
                                    "name": event.tool_name,
                                    "arguments": json.dumps(
                                        event.tool_args, ensure_ascii=False
                                    ),
                                }
                            )
                            # Responses API format: function_call_output item
                            api_messages.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": event.tool_call_id,
                                    "output": json.dumps(
                                        result, ensure_ascii=False
                                    ),
                                }
                            )
                        except Exception as e:
                            tracker.record(
                                event.tool_name, event.tool_args, str(e), ok=False
                            )
                            self._emit(
                                session_id,
                                EventType.PLAN_STEP_ERROR,
                                data={"error": str(e)},
                            )
                            api_messages.append(
                                {
                                    "type": "function_call_output",
                                    "call_id": event.tool_call_id,
                                    "output": json.dumps(
                                        {"error": str(e)}, ensure_ascii=False
                                    ),
                                }
                            )

                elif event.type == "done":
                    break

            # 补偿遗漏
            missed = tracker.missed_calls(round_tool_calls)
            for tc in missed:
                tool = self._tool_registry.get(tc["name"])
                if tool:
                    try:
                        result = await tool.handler(**tc.get("arguments", {}))
                        tracker.record(
                            tc["name"], tc.get("arguments", {}), result, ok=True
                        )
                    except Exception:
                        pass

            if not tool_called_this_round:
                break

            # TurnEnd 暂缓
            if round_num < MAX_TOOL_CALLS_PER_TURN - 1:
                summary = tracker.summary_for_prompt()
                api_messages.append(
                    {
                        "role": "system",
                        "content": f"你刚执行了工具。{summary}\n请确认工具结果后回复学生。",
                    }
                )

        # 4. 持久化
        add_message(db, session_id=int(session_id), role="agent", content=final_reply)
        self._emit(
            session_id, EventType.PLAN_DONE, data={"reply_length": len(final_reply)}
        )
        return final_reply

    async def stream_text_reply(self, session_id: str, text: str) -> None:
        """流式文本回复（通用问答场景，向后兼容）。"""
        assert self._event_bus is not None, "AgentRuntime not initialized"
        chunk_size = 20
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            self._event_bus.emit(
                AgentEvent(
                    type=EventType.CHAT_TEXT_DELTA,
                    session_id=session_id,
                    data={"delta": chunk},
                )
            )

    # ── private helpers ─────────────────────────────────────────────

    async def _stream_and_collect(
        self,
        messages: list[dict[str, Any]],
        session_id: str,
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        reply = ""
        async for event in self._llm.stream_chat(messages, tools):
            if event.type == "text_delta":
                reply += event.delta
                self._emit(
                    session_id, EventType.CHAT_TEXT_DELTA, data={"delta": event.delta}
                )
            elif event.type == "done":
                break
        return reply

    def _build_tool_schemas(self, tools: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.schema or {"type": "object", "properties": {}},
                "strict": True,
            }
            for t in tools
        ]

    def _emit(
        self,
        session_id: str,
        event_type: EventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        if self._event_bus:
            self._event_bus.emit(
                AgentEvent(
                    type=event_type, session_id=session_id, data=data or {}
                )
            )

    # ── 保留编译工作流接口（插件依赖） ─────────────────────────────

    def compile_linear_workflow(
        self, state_schema: type, steps: list[AgentStep]
    ) -> Any:
        if not steps:
            raise ValueError("Agent workflow must contain at least one step")
        graph = StateGraph(state_schema)
        for step in steps:
            graph.add_node(step.name, step.handler)
        graph.add_edge(START, steps[0].name)
        for current, next_step in zip(steps, steps[1:]):
            graph.add_edge(current.name, next_step.name)
        graph.add_edge(steps[-1].name, END)
        return graph.compile()
