"""AgentState — LangGraph state definition for the learning Agent."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # ── 输入 ──────────────────────────────────────
    session_id: str
    user_id: int
    student_message: str
    file_path: str | None
    file_data_url: str | None          # base64 dataurl for vision LLM
    file_content: str | None           # 图片/文件的文本描述

    # ── 意图识别结果 ──────────────────────────────
    intent: str                         # 意图类别枚举
    intent_confidence: float
    intent_description: str

    # ── 工具调度 ──────────────────────────────────
    tool_to_call: str | None
    tool_args: dict[str, Any] | None
    tool_result: dict[str, Any] | None

    # ── 输出 ──────────────────────────────────────
    llm_response: str
    card_type: str | None
    card_payload: dict[str, Any] | None

    # ── 上下文 ────────────────────────────────────
    messages: list[dict[str, Any]]      # 会话历史
    student_profile: dict[str, Any]     # 学生信息

    # ── 错误 ──────────────────────────────────────
    error: str | None
