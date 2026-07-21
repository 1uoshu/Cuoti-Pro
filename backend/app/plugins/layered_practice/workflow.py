from typing import Any

from app.kernel.context import KernelContext
from app.plugins.assignment_grading.workflow import normalize_question_grade, regrade_text_question
from app.plugins.layered_practice.schemas import ModelPracticePayload


DIFFICULTY_AGENT_VALUES = {
    "基础补漏": "base",
    "同类变式": "variant",
    "综合提升": "advanced",
    "高考真题": "exam",
}


async def generate_practice_questions(
    context: KernelContext,
    student_id: str,
    subject: str,
    grade: str | None,
    knowledge_point: str,
    difficulty: str,
    count: int,
    recent_mistakes: list[str],
) -> ModelPracticePayload:
    if context.capabilities.agent_api is not None:
        payload = await context.capabilities.agent_api.generate_practice(
            student_id=student_id,
            weak_points=knowledge_point,
            difficulty=DIFFICULTY_AGENT_VALUES[difficulty],
        )
        questions = _normalize_agent_practice_questions(payload)
        result = ModelPracticePayload.model_validate({"questions": questions})
        if len(result.questions) != count:
            raise ValueError("Agent practice question count does not match request")
        return result

    prompt = f"""为{grade or ""}{subject}学生生成 {count} 道“{knowledge_point}”的“{difficulty}”练习题。
历史薄弱表现：{recent_mistakes or ["暂无历史错题"]}。
只返回 JSON：
{{
  "questions": [
    {{"content": "题目", "standard_answer": "标准答案", "explanation": "完整但简洁的解析"}}
  ]
}}

题目必须可独立作答，答案必须与题目匹配，不能重复或引用不存在的图片、表格和上下文。"""
    payload = await context.capabilities.llm.chat_json(
        "你是教师题库助手，只返回有效 JSON。",
        prompt,
        temperature=0.35,
        max_tokens=3000,
    )
    result = ModelPracticePayload.model_validate(payload)
    if len(result.questions) != count:
        raise ValueError("generated practice question count does not match request")
    return result


async def grade_practice_answer(
    context: KernelContext,
    student_id: str,
    subject: str,
    question: dict[str, Any],
    student_answer: str,
) -> dict[str, Any]:
    if context.capabilities.agent_api is not None:
        payload = await context.capabilities.agent_api.answer_practice(
            student_id=student_id,
            question=question,
            student_answer=student_answer,
        )
        return normalize_question_grade(payload)
    return await regrade_text_question(
        context,
        subject,
        str(question["content"]),
        student_answer,
        str(question["standard_answer"]),
    )


def _normalize_agent_practice_questions(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_questions: Any = payload.get("questions")
    if raw_questions is None:
        for wrapper in ("data", "result", "output", "response"):
            nested = payload.get(wrapper)
            if isinstance(nested, dict) and isinstance(nested.get("questions"), list):
                raw_questions = nested["questions"]
                break
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("Agent practice result must contain a non-empty questions list")

    questions: list[dict[str, str]] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            raise ValueError("Agent practice question must be a JSON object")
        questions.append(
            {
                "content": _required_text(item, "content", "question", "question_text"),
                "standard_answer": _required_text(item, "standard_answer", "answer", "correct_answer"),
                "explanation": _required_text(item, "explanation", "analysis", "reason"),
            }
        )
    return questions


def _required_text(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise ValueError(f"Agent response is missing text field: {', '.join(keys)}")
