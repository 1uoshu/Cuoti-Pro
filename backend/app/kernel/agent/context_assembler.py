"""Context assembler — builds the prompt sent to LLM for response generation."""

from __future__ import annotations

from typing import Any

from app.kernel.agent.state import AgentState

MAX_HISTORY_MESSAGES = 20


def build_system_prompt(state: AgentState) -> str:
    """组装系统提示词：角色 + 能力 + 学生信息。"""
    profile = state.get("student_profile") or {}
    grade = profile.get("grade") or "未知年级"
    main_subject = profile.get("main_subject") or "未知学科"

    return f"""# 角色
你是「智学错题」AI 学习助手，面向中学生，帮助学生管理错题、批改作业、解答学习疑问。

# 当前学生
- 年级：{grade}
- 主学科：{main_subject}

# 回答风格
- 用简洁清晰的中文回答，适合中学生理解
- 数学公式用纯文本表示（如 x^2、√2、∫f(x)dx）
- 回答有条理，分点或分步骤
- 不确定的内容标注「仅供参考」
- 不编造数据或题目的具体内容

# 能力边界
- 你可以：批改作业、讲解题目、查询错题、解答知识问题、分析学习情况
- 你不可以：替学生做作业（只讲思路，不直接给答案）、泄露其他学生信息
- 如果学生要求超出能力范围，礼貌告知并建议替代方案

# 严格规则
- 只基于当前对话中的实际内容回答，不要假设或编造你没有看到的信息
- 不同会话之间完全独立，不要引用其他会话的内容
- 不要把你推测的常见答案当成学生实际写的答案

# 图片处理规则（重要）
「学生之前上传的附件内容」是背景参考信息。处理规则：
- 第一轮（附件刚出现、学生没有明确意图）：根据附件内容分析学生的作答状态，简短提问确认学生意图，不输出解题步骤。
- 后续轮次：根据学生当前说的话来回答。如果学生说"不会"就直接讲解，如果学生问其他问题就正常回答。不要每轮都重复问"你卡在哪里"。
- 附件内容用于理解题目上下文，但不要在每次回复中都引用它。
"""


def build_context_messages(state: AgentState) -> list[dict[str, str]]:
    """组装会话历史（最近 N 条）。"""
    raw_messages = state.get("messages") or []
    recent = raw_messages[-MAX_HISTORY_MESSAGES:]

    context: list[dict[str, str]] = []
    for msg in recent:
        role = msg.get("role", "student")
        content = msg.get("content", "")
        if not content:
            continue
        # 映射角色：student → user, agent/system → assistant
        llm_role = "user" if role == "student" else "assistant"
        context.append({"role": llm_role, "content": content})

    return context


def build_user_message(state: AgentState) -> str:
    """组装当前用户消息：文字 + 工具结果 + 附件信息。"""
    parts = []

    # 工具执行结果（如果有）
    tool_result = state.get("tool_result")
    if tool_result:
        parts.append("【系统信息：以下是工具执行结果】")
        parts.append(_format_tool_result(tool_result))
        parts.append("")

    # 文件描述（如果有，始终注入，但标注来源）
    file_content = state.get("file_content")
    if file_content:
        parts.append(f"【学生之前上传的附件内容】\n{file_content}")
        parts.append("")

    # 学生当前问题
    student_msg = state.get("student_message") or ""
    if student_msg:
        parts.append(student_msg)

    return "\n".join(parts) if parts else "..."


def _format_tool_result(result: dict[str, Any]) -> str:
    """将工具执行结果格式化为可读文本。"""
    if not result:
        return "(无结果)"

    # 错题列表
    if "wrong_questions" in result:
        items = result["wrong_questions"]
        if not items:
            return "错题本为空，暂无错题。"
        lines = [f"共 {len(items)} 道错题："]
        for i, item in enumerate(items, 1):
            kp = item.get("knowledge_point", "未知")
            reason = item.get("wrong_reason", "未知")
            lines.append(f"{i}. 知识点：{kp} | 错因：{reason}")
        return "\n".join(lines)

    # 掌握度数据
    if "weak_points" in result:
        items = result["weak_points"]
        if not items:
            return "暂无薄弱知识点数据。"
        lines = ["薄弱知识点："]
        for item in items:
            kp = item.get("knowledge_point", "未知")
            score = item.get("mastery_score", 0)
            lines.append(f"- {kp}（掌握度 {score}%）")
        return "\n".join(lines)

    # 批改结果
    if "questions" in result:
        items = result["questions"]
        total = len(items)
        wrong = sum(1 for q in items if not q.get("is_correct"))
        return f"批改完成，共 {total} 题，其中 {wrong} 题判错。"

    # 通用：JSON 序列化
    import json
    return json.dumps(result, ensure_ascii=False, indent=2)[:2000]
