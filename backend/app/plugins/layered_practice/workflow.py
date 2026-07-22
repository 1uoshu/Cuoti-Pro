from typing import Any
from typing import TypedDict

from app.kernel.agent import AgentStep, normalize_question_grade, required_text
from app.kernel.context import KernelContext
from app.plugins.assignment_grading.workflow import regrade_text_question
from app.plugins.layered_practice.prompts import PRACTICE_SYSTEM_PROMPT, build_practice_generation_prompt
from app.plugins.layered_practice.schemas import ModelPracticePayload


MAX_BUILTIN_GENERATION_ATTEMPTS = 3


class PracticeGenerationState(TypedDict, total=False):
    subject: str
    grade: str | None
    knowledge_point: str
    difficulty: str
    count: int
    recent_mistakes: list[str]
    result: ModelPracticePayload


def build_practice_workflow(context: KernelContext):
    async def prepare_context_node(state: PracticeGenerationState) -> PracticeGenerationState:
        return {"recent_mistakes": [str(item)[:1000] for item in state.get("recent_mistakes", [])[:5]]}

    async def generate_node(state: PracticeGenerationState) -> PracticeGenerationState:
        retry_feedback: str | None = None
        for _ in range(MAX_BUILTIN_GENERATION_ATTEMPTS):
            prompt = build_practice_generation_prompt(
                grade=state.get("grade"),
                subject=state["subject"],
                knowledge_point=state["knowledge_point"],
                difficulty=state["difficulty"],
                count=state["count"],
                recent_mistakes=state.get("recent_mistakes", []),
            )
            if retry_feedback:
                prompt += f"\n\n上一次输出未通过后端校验：{retry_feedback}\n请重新生成全部题目。"
            payload = await context.capabilities.llm.chat_json_with_python(
                PRACTICE_SYSTEM_PROMPT,
                prompt,
                context.capabilities.sandbox,
                temperature=0.35,
                max_tokens=3000,
            )
            try:
                result = _validate_practice_payload(payload, state["count"], state["knowledge_point"])
            except ValueError as exc:
                retry_feedback = str(exc)[:500]
                continue
            return {"result": result}
        raise ValueError(f"practice generation failed validation after retries: {retry_feedback}")

    async def validate_node(state: PracticeGenerationState) -> PracticeGenerationState:
        result = state["result"]
        for question in result.questions:
            if question.confidence < context.settings.review_confidence_threshold and not question.confidence_warning:
                question.confidence_warning = "题目与答案的验算置信度偏低，请结合解析自行判断"
        return {"result": result}

    return context.capabilities.agent_runtime.compile_linear_workflow(
        PracticeGenerationState,
        [
            AgentStep("prepare_context", prepare_context_node),
            AgentStep("generate", generate_node),
            AgentStep("validate", validate_node),
        ],
    )


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
    workflow = build_practice_workflow(context)
    state = await workflow.ainvoke(
        {
            "subject": subject,
            "grade": grade,
            "knowledge_point": knowledge_point,
            "difficulty": difficulty,
            "count": count,
            "recent_mistakes": recent_mistakes,
        }
    )
    return state["result"]


async def grade_practice_answer(
    context: KernelContext,
    student_id: str,
    subject: str,
    question: dict[str, Any],
    student_answer: str,
) -> dict[str, Any]:
    return await regrade_text_question(
        context,
        subject,
        str(question["content"]),
        student_answer,
        str(question["standard_answer"]),
    )


def _validate_practice_payload(
    payload: dict[str, Any],
    expected_count: int,
    expected_knowledge_point: str,
) -> ModelPracticePayload:
    try:
        result = ModelPracticePayload.model_validate(payload)
    except ValueError as exc:
        raise ValueError(f"generated practice payload is invalid: {exc}") from exc
    if len(result.questions) != expected_count:
        raise ValueError("generated practice question count does not match request")
    if any(question.knowledge_point.strip() != expected_knowledge_point for question in result.questions):
        raise ValueError(f'generated questions must use knowledge_point "{expected_knowledge_point}" exactly')
    return result
