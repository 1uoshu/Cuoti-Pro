from typing import Any
from typing import TypedDict

from app.kernel.agent import AgentStep, normalize_question_grade, required_text
from app.kernel.context import KernelContext
from app.plugins.assignment_grading.workflow import regrade_text_question
from app.plugins.layered_practice.prompts import PRACTICE_SYSTEM_PROMPT, build_practice_generation_prompt
from app.plugins.layered_practice.schemas import ModelPracticePayload


DIFFICULTY_AGENT_VALUES = {
    "基础补漏": "base",
    "同类变式": "variant",
    "综合提升": "advanced",
    "高考真题": "exam",
}


class PracticeGenerationState(TypedDict, total=False):
    subject: str
    grade: str | None
    knowledge_point: str
    difficulty: str
    count: int
    recent_mistakes: list[str]
    raw_payload: dict[str, Any]
    result: ModelPracticePayload


def build_practice_workflow(context: KernelContext):
    async def prepare_context_node(state: PracticeGenerationState) -> PracticeGenerationState:
        return {"recent_mistakes": [str(item)[:1000] for item in state.get("recent_mistakes", [])[:5]]}

    async def generate_node(state: PracticeGenerationState) -> PracticeGenerationState:
        payload = await context.capabilities.llm.chat_json_with_python(
            PRACTICE_SYSTEM_PROMPT,
            build_practice_generation_prompt(
                grade=state.get("grade"),
                subject=state["subject"],
                knowledge_point=state["knowledge_point"],
                difficulty=state["difficulty"],
                count=state["count"],
                recent_mistakes=state.get("recent_mistakes", []),
            ),
            context.capabilities.sandbox,
            temperature=0.35,
            max_tokens=3000,
        )
        return {"raw_payload": payload}

    async def validate_node(state: PracticeGenerationState) -> PracticeGenerationState:
        result = ModelPracticePayload.model_validate(state["raw_payload"])
        if len(result.questions) != state["count"]:
            raise ValueError("generated practice question count does not match request")
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
    if context.capabilities.agent_api is not None:
        unique_questions: dict[str, dict[str, str]] = {}
        attempts = 0
        while len(unique_questions) < count and attempts < count * 3:
            attempts += 1
            payload = await context.capabilities.agent_api.generate_practice(
                student_id=student_id,
                weak_points=knowledge_point,
                difficulty=DIFFICULTY_AGENT_VALUES[difficulty],
            )
            for question in _normalize_agent_practice_questions(payload):
                unique_questions.setdefault(question["content"], question)
        if len(unique_questions) < count:
            raise ValueError("Agent practice question count does not match request")
        return ModelPracticePayload.model_validate({"questions": list(unique_questions.values())[:count]})

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
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("Agent practice result must contain a non-empty questions list")

    questions: list[dict[str, str]] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            raise ValueError("Agent practice question must be a JSON object")
        questions.append(
            {
                "content": required_text(item, "content", "question", "question_text"),
                "standard_answer": required_text(item, "standard_answer", "answer", "correct_answer"),
                "explanation": required_text(item, "explanation", "analysis", "reason"),
                "confidence": float(item.get("confidence", 0)),
                "confidence_warning": item.get("confidence_warning") or "外部 Agent 未提供可靠验算置信度，请自行判断",
            }
        )
    return questions
