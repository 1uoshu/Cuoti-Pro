from typing import TypedDict

from app.kernel.agent import AgentStep
from app.kernel.context import KernelContext
from app.plugins.stage_assessment.prompts import EXAM_SYSTEM_PROMPT, build_exam_generation_prompt
from app.plugins.stage_assessment.schemas import ModelExamPayload


MAX_GENERATION_ATTEMPTS = 3


class ExamGenerationState(TypedDict, total=False):
    grade: str | None
    subject: str
    exam_type: str
    knowledge_points: list[str]
    difficulty: str
    count: int
    recent_mistakes: list[str]
    result: ModelExamPayload


def build_exam_workflow(context: KernelContext):
    async def generate_node(state: ExamGenerationState) -> ExamGenerationState:
        feedback: str | None = None
        for _ in range(MAX_GENERATION_ATTEMPTS):
            prompt = build_exam_generation_prompt(
                grade=state.get("grade"),
                subject=state["subject"],
                exam_type=state["exam_type"],
                knowledge_points=state["knowledge_points"],
                difficulty=state["difficulty"],
                count=state["count"],
                recent_mistakes=state.get("recent_mistakes", []),
            )
            if feedback:
                prompt += f"\n上一次输出未通过后端校验：{feedback}\n请重新生成全部题目。"
            raw = await context.capabilities.llm.chat_json_with_python(
                EXAM_SYSTEM_PROMPT,
                prompt,
                context.capabilities.sandbox,
                temperature=0.3,
                max_tokens=6000,
            )
            try:
                result = _validate_payload(raw, state["count"], state["knowledge_points"])
            except ValueError as exc:
                feedback = str(exc)[:500]
                continue
            return {"result": result}
        raise ValueError(f"exam generation failed validation after retries: {feedback}")

    async def confidence_node(state: ExamGenerationState) -> ExamGenerationState:
        result = state["result"]
        for question in result.questions:
            if question.confidence < context.settings.review_confidence_threshold and not question.confidence_warning:
                question.confidence_warning = "题目与答案的验算置信度偏低，请结合解析自行判断"
        return {"result": result}

    return context.capabilities.agent_runtime.compile_linear_workflow(
        ExamGenerationState,
        [AgentStep("generate", generate_node), AgentStep("validate", confidence_node)],
    )


async def generate_exam_questions(
    context: KernelContext,
    *,
    grade: str | None,
    subject: str,
    exam_type: str,
    knowledge_points: list[str],
    difficulty: str,
    count: int,
    recent_mistakes: list[str],
) -> ModelExamPayload:
    state = await build_exam_workflow(context).ainvoke(
        {
            "grade": grade,
            "subject": subject,
            "exam_type": exam_type,
            "knowledge_points": knowledge_points,
            "difficulty": difficulty,
            "count": count,
            "recent_mistakes": recent_mistakes,
        }
    )
    return state["result"]


def _validate_payload(payload: dict, expected_count: int, knowledge_points: list[str]) -> ModelExamPayload:
    try:
        result = ModelExamPayload.model_validate(payload)
    except ValueError as exc:
        raise ValueError(f"generated exam payload is invalid: {exc}") from exc
    if len(result.questions) != expected_count:
        raise ValueError("generated exam question count does not match request")
    allowed = set(knowledge_points)
    if any(question.knowledge_point not in allowed for question in result.questions):
        raise ValueError("generated exam contains a knowledge point outside the requested scope")
    return result
