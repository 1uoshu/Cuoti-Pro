"""Agent runtime — LangGraph StateGraph for the learning Agent.

Rewrites the previous 27-line linear workflow into a full intent-driven runtime.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, START, StateGraph

from app.kernel.agent.context_assembler import build_context_messages, build_system_prompt, build_user_message
from app.kernel.agent.intent_router import (
    INTENT_ANSWER_VERIFICATION,
    INTENT_GENERAL_CHAT,
    INTENT_HOMEWORK_GRADING,
    INTENT_KNOWLEDGE_QUESTION,
    INTENT_PRACTICE_REQUEST,
    INTENT_QUESTION_EXPLANATION,
    INTENT_UNCLEAR,
    run_intent_router,
)
from app.kernel.agent.state import AgentState

if TYPE_CHECKING:
    from app.kernel.context import KernelContext


@dataclass(frozen=True)
class AgentStep:
    name: str
    handler: Callable[[Any], Any]


class AgentRuntime:
    """Kernel-owned LangGraph helper used by plugins to build workflows."""

    def __init__(self, context: KernelContext):
        self._context = context

    def compile_agent_workflow(self):
        """编译 Agent 主工作流：input → intent → tool → response → END。"""
        graph = StateGraph(AgentState)

        graph.add_node("input_processor", self._input_processor)
        graph.add_node("intent_router", self._intent_router)
        graph.add_node("tool_executor", self._tool_executor)
        graph.add_node("response_builder", self._response_builder)

        graph.add_edge(START, "input_processor")
        graph.add_edge("input_processor", "intent_router")
        graph.add_conditional_edges(
            "intent_router",
            self._route_after_intent,
            {
                "needs_tool": "tool_executor",
                "direct_response": "response_builder",
            },
        )
        graph.add_edge("tool_executor", "response_builder")
        graph.add_edge("response_builder", END)

        return graph.compile()

    # ── 节点实现 ──────────────────────────────────

    async def _input_processor(self, state: AgentState) -> AgentState:
        """解析学生输入：提取文字、处理文件。"""
        file_path = state.get("file_path")
        file_data_url = state.get("file_data_url")
        file_content = state.get("file_content")

        # 如果有图片但没有描述，调用视觉 LLM 生成描述
        if file_data_url and not file_content:
            try:
                file_content = await self._context.capabilities.llm.vision_chat_completions(
                    system_prompt=(
                        "你是一个图片内容识别助手。请严格按图片中的实际内容进行描述。\n"
                        "重要规则：\n"
                        "1. 只描述图片中实际存在的文字和内容，不要推测或编造\n"
                        "2. 不要假设图片中不存在的内容\n\n"
                        "请按以下结构输出：\n"
                        "- 题目内容：逐题列出所有题目文字\n"
                        "- 手写内容：图片中是否存在手写内容？如果有，逐字识别手写文字\n"
                        "- 作答状态：如果有手写内容，判断学生是否完成了作答（有完整解题过程=已作答，只有部分步骤或空白=未完成）\n"
                        "- 学科判断：根据题目内容判断属于哪个学科"
                    ),
                    user_prompt="请按上述结构逐题分析这张图片的内容。",
                    image_data_url=file_data_url,
                    temperature=0.1,
                    max_tokens=2048,
                )
            except Exception:
                file_content = "[图片内容识别失败]"

        return {
            **state,
            "file_content": file_content,
        }

    async def _intent_router(self, state: AgentState) -> AgentState:
        """调用 LLM 进行意图识别。"""
        return await run_intent_router(state, self._context)

    async def _tool_executor(self, state: AgentState) -> AgentState:
        """根据意图调用对应工具。当前为占位实现。"""
        tool_address = state.get("tool_to_call")
        if not tool_address:
            return state

        # TODO: 接入真实的工具调用
        # 当前返回占位结果
        return {
            **state,
            "tool_result": {"status": "placeholder", "tool": tool_address},
        }

    async def _response_builder(self, state: AgentState) -> AgentState:
        """组装上下文，调用 LLM 生成回复。"""
        llm = self._context.capabilities.llm

        system_prompt = build_system_prompt(state)
        context_messages = build_context_messages(state)
        user_message = build_user_message(state)

        # 如果是练习请求（场景2未开放），直接返回提示
        if state.get("intent") == INTENT_PRACTICE_REQUEST:
            return {
                **state,
                "llm_response": "分层练习功能即将开放，敬请期待！目前你可以通过上传作业来获取批改和错题分析。",
                "card_type": None,
                "card_payload": None,
            }

        try:
            # 使用 chat_completions_text（兼容 DeepSeek 等非 OpenAI 供应商）
            response_text = await llm.chat_completions_text(
                system_prompt=system_prompt,
                user_prompt=user_message,
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception:
            response_text = "抱歉，我暂时无法回答这个问题，请稍后再试。"

        return {
            **state,
            "llm_response": response_text,
            "card_type": None,
            "card_payload": None,
        }

    # ── 条件路由 ──────────────────────────────────

    def _route_after_intent(self, state: AgentState) -> str:
        """意图识别后决定走工具还是直接回答。"""
        intent = state.get("intent", INTENT_UNCLEAR)
        tool = state.get("tool_to_call")

        # 需要调工具的意图
        if tool and intent not in {
            INTENT_GENERAL_CHAT,
            INTENT_KNOWLEDGE_QUESTION,
            INTENT_QUESTION_EXPLANATION,
            INTENT_ANSWER_VERIFICATION,
            INTENT_UNCLEAR,
        }:
            return "needs_tool"

        return "direct_response"

    # ── 旧接口兼容 ────────────────────────────────

    def compile_linear_workflow(self, state_schema: type, steps: list[AgentStep]):
        """保留旧的线性工作流编译方法，供其他插件使用。"""
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
