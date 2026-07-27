"""Intent router node — uses LLM to identify student intent."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.kernel.agent.state import AgentState

if TYPE_CHECKING:
    from app.kernel.context import KernelContext

# ── 意图类别枚举 ──────────────────────────────────

INTENT_HOMEWORK_GRADING = "homework_grading"
INTENT_QUESTION_EXPLANATION = "question_explanation"
INTENT_ERROR_ANALYSIS = "error_analysis"
INTENT_ANSWER_VERIFICATION = "answer_verification"
INTENT_KNOWLEDGE_POINT_ID = "knowledge_point_id"
INTENT_WRONG_QUESTION_QUERY = "wrong_question_query"
INTENT_KNOWLEDGE_QUESTION = "knowledge_question"
INTENT_MANUAL_ARCHIVE = "manual_archive"
INTENT_LEARNING_ANALYSIS = "learning_analysis"
INTENT_PRACTICE_REQUEST = "practice_request"
INTENT_SESSION_MANAGEMENT = "session_management"
INTENT_GENERAL_CHAT = "general_chat"
INTENT_UNCLEAR = "unclear"

# 意图 → 工具地址映射
INTENT_TOOL_MAP: dict[str, str | None] = {
    INTENT_HOMEWORK_GRADING: "AssignmentGrading::UploadAndGrade",
    INTENT_ERROR_ANALYSIS: "WrongQuestionBook::List",
    INTENT_WRONG_QUESTION_QUERY: "WrongQuestionBook::List",
    INTENT_MANUAL_ARCHIVE: "WrongQuestionBook::Archive",
    INTENT_LEARNING_ANALYSIS: "MasteryTracking::GetWeakPoints",
    INTENT_QUESTION_EXPLANATION: None,
    INTENT_ANSWER_VERIFICATION: None,
    INTENT_KNOWLEDGE_POINT_ID: None,
    INTENT_KNOWLEDGE_QUESTION: None,
    INTENT_PRACTICE_REQUEST: None,
    INTENT_SESSION_MANAGEMENT: None,
    INTENT_GENERAL_CHAT: None,
    INTENT_UNCLEAR: None,
}

# ── 系统提示词 ────────────────────────────────────

INTENT_SYSTEM_PROMPT = """# 角色
你是「智学错题」AI 学习助手，面向中学生，专注于帮助学生管理错题、批改作业、解答学习疑问。

# 核心能力
1. 作业/试卷批改：识别图片中的题目和手写答案，逐题判分、标注知识点、自动归档错题
2. 题目讲解：针对具体题目提供详细的解题思路和步骤
3. 错题管理：查询错题本、分析错因、跟踪复习进度
4. 知识问答：解答学科知识问题，讲解概念和公式
5. 学习分析：分析学生薄弱知识点，提供学习建议

# 意图识别规则

当收到学生消息时，你需要判断学生的真实意图。规则如下（按优先级从高到低）：

## 规则 1：有文件 + 批改意图
- 触发词：「批改」「检查」「改一下」「帮我看看对不对」「判分」「评分」
- → 意图：homework_grading

## 规则 1b：有文件 + 无文字说明（只传图不说话）
- 附带文字为「用户上传了文件，未附带文字说明」或类似空描述
- 此时不要假设意图，应标记为 unclear，让 Agent 分析图片后追问学生
- → 意图：unclear

## 规则 2：有文件 + 题目讲解意图
- 触发词：「第X题怎么做」「这道题怎么解」「讲解一下」「解题思路」「怎么算」「怎么证明」「教我」「思路」
- → 意图：question_explanation

## 规则 3：有文件 + 错因分析意图
- 触发词：「为什么判错」「哪里错了」「错因」「为什么不对」「错在哪」「为什么扣分」
- → 意图：error_analysis

## 规则 4：有文件 + 答案校验意图
- 触发词：「老师说答案是X」「帮我确认」「答案对不对」「答案是不是X」「正确答案是什么」「我的答案对吗」
- → 意图：answer_verification

## 规则 5：有文件 + 知识点识别意图
- 触发词：「什么知识点」「考的什么」「属于哪个章节」「这道题的考点」「涉及什么知识」
- → 意图：knowledge_point_id

## 规则 6：有文件 + 手动归档意图
- 触发词：「整理进错题本」「归档」「记到错题本」「收录」「保存到错题本」「加到错题本」
- → 意图：manual_archive

## 规则 7：无文件 + 错题查询意图
- 触发词：「错题」「错题本」「我的错题」「有哪些错题」「XX的错题」「错了几次」「复习错题」「看看错题」
- → 意图：wrong_question_query

## 规则 8：无文件 + 学习分析意图
- 触发词：「最近学习怎么样」「哪些知识点薄弱」「成绩有进步吗」「学习情况」「薄弱点」「弱项」
- → 意图：learning_analysis

## 规则 9：无文件 + 练习请求意图
- 触发词：「出几道题」「练一下」「做点练习」「练练XX」「出题」「给我出题」
- → 意图：practice_request

## 规则 10：无文件 + 会话管理意图
- 触发词：「新建会话」「新对话」「改标题」「之前的聊天」「历史记录」
- → 意图：session_management

## 规则 11：无文件 + 知识问答意图
- 触发词：「XX怎么理解」「XX是什么」「帮我讲讲」「XX的定义」「XX公式」「怎么推导」
- 或任何学科相关的问题
- → 意图：knowledge_question

## 规则 12：通用聊天
- 问候、闲聊、自我介绍请求等
- → 意图：general_chat

## 规则 13：意图不明确
- 消息过于模糊、无法判断具体意图
- → 意图：unclear（追问学生具体需求）

# 输出格式

你必须严格按照以下 JSON 格式输出意图识别结果，不要输出其他内容：

```json
{
  "intent": "<意图类别>",
  "confidence": <0.0-1.0>,
  "description": "<一句话描述你对学生意图的理解>",
  "reasoning": "<你的判断依据，引用学生消息中的关键词>"
}
```

# 注意事项
- 当学生消息同时包含多种意图时，选择最明确/最具体的一个
- 文件默认视为「作业/试卷」进行批改，除非文字明确指向其他意图
- 不确定时优先选择 confidence 较低的意图，而不是猜
- 你只负责识别意图，不负责执行。执行由系统根据你的意图结果调度
"""


def _build_user_prompt(state: AgentState) -> str:
    """组装发给 LLM 的用户消息。"""
    parts = ["【学生消息】"]
    parts.append(state.get("student_message") or "(无文字)")

    parts.append("\n【附件内容】")
    if state.get("file_content"):
        parts.append(state["file_content"])
    elif state.get("file_path"):
        parts.append("[已上传文件，正在识别中]")
    else:
        parts.append("无附件")

    profile = state.get("student_profile") or {}
    parts.append(f"\n【学生信息】")
    parts.append(f"年级：{profile.get('grade') or '未知'}")
    parts.append(f"主学科：{profile.get('main_subject') or '未知'}")

    return "\n".join(parts)


async def run_intent_router(state: AgentState, context: KernelContext) -> AgentState:
    """LangGraph node: 意图识别。"""
    llm = context.capabilities.llm

    user_prompt = _build_user_prompt(state)

    try:
        result = await llm.chat_completions_json(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=512,
        )
    except Exception:
        # LLM 调用失败时回退到默认意图
        has_file = bool(state.get("file_path"))
        return {
            **state,
            "intent": INTENT_HOMEWORK_GRADING if has_file else INTENT_GENERAL_CHAT,
            "intent_confidence": 0.5,
            "intent_description": "意图识别失败，默认处理",
            "tool_to_call": INTENT_TOOL_MAP.get(INTENT_HOMEWORK_GRADING if has_file else INTENT_GENERAL_CHAT),
        }

    intent = result.get("intent", INTENT_UNCLEAR)
    confidence = float(result.get("confidence", 0.5))
    description = result.get("description", "")
    tool_to_call = INTENT_TOOL_MAP.get(intent)

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "intent_description": description,
        "tool_to_call": tool_to_call,
    }
