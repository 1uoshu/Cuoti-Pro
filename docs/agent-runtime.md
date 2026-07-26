# Agent 运行时设计文档

版本：v1.0（2026-07-27）
关联接口文档：`API接口文档.md` v2.1 §8.6

---

## 1. 运行时概述

Agent 运行时基于 LangGraph `StateGraph` 构建，是整个 chat 系统的调度核心。
负责：接收学生消息 → 意图识别 → 决定调工具还是直接回答 → 执行 → 组装回复。

设计原则：
- Planner 与 Executor 是两个独立接缝，本期 Planner 只产出单目标简单 Plan
- 新增 Agent 能力 = 加一个插件 Tool，永不改运行时骨架
- 将来升级多步 DAG / Plan Revision / 中断取消都是往接缝里填，不动骨架

---

## 2. AgentState 状态定义

```python
from typing import TypedDict

class AgentState(TypedDict):
    # 输入
    session_id: str              # 会话 ID
    user_id: int                 # 学生 ID
    student_message: str         # 学生发送的文字（可能为空）
    file_path: str | None        # 上传的文件路径（可能为空）
    file_content: str | None     # 文件识别后的文本/图片描述（图片由视觉 LLM 生成）

    # 意图识别结果
    intent: str                  # 意图类别（见 §3）
    intent_confidence: float     # 意图置信度（0-1）
    intent_description: str      # 一句话描述学生意图

    # 工具调度
    tool_to_call: str | None     # 决定调用的工具地址（如 "AssignmentGrading::UploadAndGrade"）
    tool_args: dict | None       # 工具参数
    tool_result: dict | None     # 工具执行结果

    # 输出
    llm_response: str            # LLM 文字回复（流式累积）
    card_type: str | None        # 卡片类型（grading / student_exercise / wrong_question / upload_failed / null）
    card_payload: dict | None    # 卡片结构化数据

    # 上下文
    messages: list               # 会话历史消息（用于上下文组装）
    student_profile: dict        # 学生信息（grade, main_subject 等）

    # 错误
    error: str | None            # 错误信息
```

---

## 3. 意图类别枚举

| intent 值 | 含义 | 触发条件 | 执行动作 |
| --- | --- | --- | --- |
| `homework_grading` | 作业批改 | 有文件 + 无特定文字 / 文字含"批改""检查""改一下" | 调 `AssignmentGrading::UploadAndGrade` |
| `question_explanation` | 题目讲解 | 有文件 + "第X题怎么做""这道题怎么解""讲解一下" | LLM 读图 + 直接讲解指定题目 |
| `error_analysis` | 错因分析 | 有文件 + "为什么判错""哪里错了""错因" / 无文件 + "这道题为什么错" | LLM 结合图片/错题记录分析 |
| `answer_verification` | 答案校验 | 有文件 + "老师说答案是X""帮我确认""答案对不对" | LLM 读图 + 对比分析 |
| `knowledge_point_id` | 知识点识别 | 有文件 + "什么知识点""考的什么""属于哪个章节" | LLM 读图 + 识别知识点 |
| `wrong_question_query` | 错题查询 | 无文件 + "错题""错题本""我的错题""有哪些错题" | 调错题本查询工具 |
| `knowledge_question` | 知识问答 | 无文件 + "XX怎么理解""XX是什么""帮我讲讲XX" | LLM 直接回答 |
| `manual_archive` | 手动归档 | 有文件 + "整理进错题本""归档""记到错题本" | 调错题本归档工具 |
| `learning_analysis` | 学习分析 | 无文件 + "最近学习怎么样""哪些知识点薄弱" | 查询掌握度数据 + LLM 分析 |
| `practice_request` | 练习请求 | 无文件 + "出几道题""练一下XX""做点练习" | 提示"分层练习功能即将开放" |
| `session_management` | 会话管理 | 无文件 + "新建会话""改个标题""之前的对话" | 执行会话管理操作 |
| `general_chat` | 通用聊天 | 以上都不匹配的纯文字 | LLM 直接流式回答 |
| `unclear` | 无法识别 | 意图模糊、信息不足 | LLM 追问"你想让我帮你做什么？" |

---

## 4. StateGraph 节点与流转

```
┌─────────────┐
│   START     │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  input_processor │  ← 解析学生输入：提取文字、保存文件、识别文件内容
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  intent_router   │  ← 意图识别：调用 LLM + 系统提示词，判断学生意图
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  tool_executor   │  ← 如果需要调工具，执行对应的 Tool；否则跳过
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  response_builder│  ← 组装最终回复：文字 / 卡片 / 流式文本
└──────┬──────────┘
       │
       ▼
┌─────────────┐
│    END      │
└─────────────┘
```

### 4.1 input_processor 节点

职责：解析学生输入，准备 AgentState 的初始数据。

逻辑：
1. 从 `student_message` 提取文字内容
2. 如果有 `file_path`，将文件转为 dataurl（图片直接转，PDF 用 fitz 逐页渲染）
3. 如果有图片，调用 LLM 视觉能力生成图片内容描述（`file_content`）
4. 从数据库加载会话历史消息（`messages`）
5. 从数据库加载学生信息（`student_profile`）

### 4.2 intent_router 节点

职责：调用 LLM 进行意图识别。

逻辑：
1. 拼装意图识别 prompt（见 `docs/prompts/intent-recognition.md`）
2. 将学生文字 + 图片描述发送给 LLM
3. 解析 LLM 返回的 JSON，填充 `intent`、`intent_confidence`、`intent_description`
4. 发送 `intent.recognized` WebSocket 事件

### 4.3 tool_executor 节点

职责：根据 `intent` 决定是否调用工具，以及调用哪个工具。

调度映射：

| intent | 调用的工具 |
| --- | --- |
| `homework_grading` | `AssignmentGrading::UploadAndGrade` |
| `error_analysis` | `WrongQuestionBook::List`（查相关错题） |
| `wrong_question_query` | `WrongQuestionBook::List` |
| `manual_archive` | `WrongQuestionBook::Archive` |
| `learning_analysis` | `MasteryTracking::GetWeakPoints` |
| 其他 intent | 不调工具（跳过） |

执行前发送 `plan.start` 和 `plan.step.tool_call`（Proposal）事件。
执行后发送 `plan.step.tool_result` 或 `plan.step.error` 事件。

### 4.4 response_builder 节点

职责：组装最终回复，发送给学生。

逻辑：
1. 拼装上下文 prompt（见 §5 Context Assembler）
2. 如果有 `tool_result`，将工具结果注入上下文
3. 调用 LLM 生成回复（流式：通过 `chat.text.delta` 事件推送）
4. 持久化 agent 消息到 `chat_messages` 表
5. 发送 `plan.done` 事件

---

## 5. 上下文组装（Context Assembler）

`response_builder` 节点在调用 LLM 前，按以下顺序组装 prompt：

```
[系统提示词 — 包含角色定义、能力说明、当前学生信息]
[会话历史 — 最近 20 条消息，含 student/agent 角色]
[当前工具执行结果 — 如果有]
[当前学生问题 — 文字 + 图片描述（如果有）]
```

规则：
- 系统提示词前缀保持稳定，不随会话变化
- 会话历史取最近 20 条消息（超出截断，保留最新的）
- 学生信息（年级、学科偏好）注入系统提示词，实现基础个性化
- 工具结果以结构化文本注入（如错题列表 JSON → 格式化为可读文本）

---

## 6. 工具注册表（场景 1）

| 工具地址 | side_effect | requires_confirmation | autonomous | 说明 |
| --- | --- | --- | --- | --- |
| `AssignmentGrading::UploadAndGrade` | write | false | false | 作业批改（学生显式触发） |
| `WrongQuestionBook::List` | read | false | true | 查询错题列表 |
| `WrongQuestionBook::GetDetail` | read | false | true | 查询错题详情 |
| `WrongQuestionBook::Archive` | write | false | false | 手动归档错题 |
| `WrongQuestionBook::UpdateStatus` | write | false | false | 更新错题状态 |
| `MasteryTracking::GetWeakPoints` | read | false | true | 查询薄弱知识点 |
| `MasteryTracking::GetMastery` | read | false | true | 查询掌握度数据 |

- `autonomous=true`：Agent 可自主决定调用（如查错题列表），无需学生显式触发
- `autonomous=false`：需要学生明确意图才调用（如批改、归档）

---

## 7. WebSocket 事件发射时机

| 节点 | 发送的事件 |
| --- | --- |
| intent_router 完成 | `intent.recognized` |
| tool_executor 开始 | `plan.start` + `plan.step.tool_call`（Proposal） |
| tool_executor 执行中 | `plan.step.started` |
| tool_executor 完成 | `plan.step.tool_result` + `plan.step.done` |
| tool_executor 失败 | `plan.step.error` |
| response_builder 流式输出 | `chat.text.delta`（多次） |
| 全部完成 | `plan.done` |
