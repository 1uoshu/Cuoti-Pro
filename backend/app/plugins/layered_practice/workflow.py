from app.kernel.context import KernelContext
from app.plugins.layered_practice.schemas import ModelPracticePayload


async def generate_practice_questions(
    context: KernelContext,
    subject: str,
    grade: str | None,
    knowledge_point: str,
    difficulty: str,
    count: int,
    recent_mistakes: list[str],
) -> ModelPracticePayload:
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
