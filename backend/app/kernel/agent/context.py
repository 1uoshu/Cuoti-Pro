"""Context Assembler — 组装 Agent 的 system prompt 和消息列表。

职责：
1. 加载可配置的身份文档（identity/*.md）
2. 构建 system prompt（身份 + 工具目录 + 学生信息）
3. 组装 Responses API 格式的消息列表

借鉴 rust_code_cli 的 prompt 组装策略：稳定前缀优先。
ADR 0015: Context Assembly and Prompt Caching
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.kernel.agent.tools import ToolSpec

IDENTITY_DIR = Path(__file__).parent / "identity"

DEFAULT_IDENTITY = """你是一个面向中学生的学习助手。用通俗易懂的中文回答问题，不直接给答案，引导学生思考。"""


def load_identity(name: str = "agent") -> str:
    """从 identity/*.md 加载身份文档。

    Args:
        name: 身份文档名（不含 .md 后缀）

    Returns:
        身份文档内容，文件不存在时返回默认值
    """
    path = IDENTITY_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_IDENTITY


def build_system_prompt(
    identity: str,
    tools: list[ToolSpec],
    user_profile: dict[str, Any] | None = None,
) -> str:
    """组装 system prompt（稳定前缀优先）。

    组装顺序（借鉴 ADR 0015）：
    1. 身份文档（稳定）
    2. 学生信息（半稳定）
    3. 工具目录（稳定，除非插件变化）
    4. 行为规则（稳定）

    Args:
        identity: 身份文档内容
        tools: 可用工具列表
        user_profile: 学生信息（grade, main_subject 等）

    Returns:
        完整的 system prompt 字符串
    """
    parts = [identity.strip()]

    # 学生信息
    if user_profile:
        grade = user_profile.get("grade", "")
        subject = user_profile.get("main_subject", "")
        if grade or subject:
            parts.append(f"\n## 当前学生信息\n- 年级：{grade or '未知'}\n- 主要学科：{subject or '未知'}")

    # 工具目录
    if tools:
        tool_lines = []
        for t in tools:
            tool_lines.append(f"- **{t.name}**: {t.short_intent} | 副作用: {t.side_effect.value}")
        parts.append(f"\n## 可用工具\n" + "\n".join(tool_lines))

    # 行为规则
    parts.append("""
## 行为规则

- 如果学生的问题可以用文字回答，直接回答，不要调用工具
- 如果需要调用工具，先简短说明你要做什么（如「我来帮你批改这份作业」），然后调用工具
- 工具执行后，根据结果回复学生，不要重复工具返回的原始数据
- 每个问题最多调用 5 次工具，之后必须给出最终回复
- 如果工具执行失败，友好地告诉学生原因和建议""")

    return "\n".join(parts)


def assemble_messages(
    system_prompt: str,
    history: list[dict[str, str]],
    current_message: str,
) -> list[dict[str, Any]]:
    """组装 Responses API 格式的消息列表。

    Args:
        system_prompt: 完整的 system prompt
        history: 对话历史（API 格式，role=user/assistant）
        current_message: 当前学生消息

    Returns:
        Responses API input 消息列表
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": current_message})
    return messages


def convert_history_to_api(
    db_messages: list[Any],
) -> list[dict[str, str]]:
    """将数据库 ChatMessage 转换为 API 格式。

    Args:
        db_messages: 数据库 ChatMessage 对象列表

    Returns:
        API 格式消息列表（role: user/assistant）
    """
    api_messages = []
    for msg in db_messages:
        role = "user" if msg.role == "student" else "assistant"
        api_messages.append({"role": role, "content": msg.content})
    return api_messages
