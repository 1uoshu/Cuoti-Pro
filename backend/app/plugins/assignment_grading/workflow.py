import base64
from pathlib import Path
from typing import Any, TypedDict

import fitz

from app.kernel.agent import AgentStep, as_float, first, normalize_question_grade, optional_text, required_text
from app.kernel.context import KernelContext
from app.plugins.assignment_grading.prompts import (
    GRADING_SYSTEM_PROMPT,
    REGRADE_SYSTEM_PROMPT,
    build_assignment_grading_prompt,
    build_question_regrade_prompt,
)
from app.plugins.assignment_grading.schemas import ModelGradePayload


class GradingState(TypedDict, total=False):
    file_path: str
    student_id: str
    subject: str
    grade: str | None
    image_data_urls: list[str]
    result: ModelGradePayload


def _load_upload_as_data_urls(file_path: str) -> list[str]:
    path = Path(file_path)
    if path.suffix.lower() != ".pdf":
        media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return [f"data:{media_type};base64,{encoded}"]

    document = fitz.open(path)
    try:
        pages = []
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append(f"data:image/png;base64,{encoded}")
        return pages
    finally:
        document.close()


def build_grading_workflow(context: KernelContext):
    async def load_node(state: GradingState) -> GradingState:
        if context.capabilities.agent_api is not None:
            return {}
        return {"image_data_urls": _load_upload_as_data_urls(state["file_path"])}

    async def grade_node(state: GradingState) -> GradingState:
        grade_label = state.get("grade") or ""
        subject = state["subject"]
        if context.capabilities.agent_api is not None:
            payload = await context.capabilities.agent_api.grade_file(
                student_id=state["student_id"],
                file_path=Path(state["file_path"]),
                question=(
                    f"请识别并批改这份{grade_label}{subject}作业中的全部题目，"
                    "返回逐题题干、学生答案、正确答案、分值、对错、知识点和解析。"
                ),
                subject=subject,
            )
            return {"result": _normalize_agent_grade_payload(payload, subject)}

        data = await context.capabilities.llm.vision_json_many_with_python(
            GRADING_SYSTEM_PROMPT,
            build_assignment_grading_prompt(grade=grade_label, subject=subject),
            state["image_data_urls"],
            context.capabilities.sandbox,
            temperature=0.1,
            max_tokens=8000,
        )
        return {"result": ModelGradePayload.model_validate(data)}

    return context.capabilities.agent_runtime.compile_linear_workflow(
        GradingState,
        [
            AgentStep("load", load_node),
            AgentStep("grade", grade_node),
        ],
    )


async def run_grading_workflow(
    context: KernelContext,
    file_path: str,
    subject: str,
    grade: str | None,
    *,
    student_id: str,
) -> ModelGradePayload:
    graph = build_grading_workflow(context)
    result = await graph.ainvoke(
        {"file_path": file_path, "student_id": student_id, "subject": subject, "grade": grade}
    )
    return result["result"]


async def regrade_text_question(
    context: KernelContext,
    subject: str,
    question_text: str,
    student_answer: str | None,
    correct_answer: str | None,
    *,
    student_id: str | None = None,
) -> dict:
    if context.capabilities.agent_api is not None:
        if student_id is None:
            raise ValueError("student_id is required for Agent API grading")
        payload = await context.capabilities.agent_api.grade_text(
            student_id=student_id,
            question=f"{question_text}\n参考答案：{correct_answer or '请推导正确答案'}",
            student_answer=student_answer or "",
            subject=subject,
        )
        return normalize_question_grade(payload, default_confidence=0)

    data = await context.capabilities.llm.chat_json_with_python(
        REGRADE_SYSTEM_PROMPT,
        build_question_regrade_prompt(
            subject=subject,
            question_text=question_text,
            student_answer=student_answer,
            correct_answer=correct_answer,
        ),
        context.capabilities.sandbox,
        temperature=0.1,
        max_tokens=800,
    )
    required = {"is_correct", "score", "max_score", "explanation", "confidence"}
    if not required.issubset(data):
        raise ValueError("model regrade result is missing required fields")
    return data


def _normalize_agent_grade_payload(payload: dict[str, Any], subject: str) -> ModelGradePayload:
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("Agent grading result must contain a non-empty questions list")

    questions: list[dict[str, Any]] = []
    for index, raw_question in enumerate(raw_questions, start=1):
        if not isinstance(raw_question, dict):
            raise ValueError("Agent grading question must be a JSON object")
        grade = normalize_question_grade(raw_question, default_confidence=0)
        questions.append(
            {
                "question_number": str(first(raw_question, "question_number", "number", default=index)),
                "question_text": required_text(raw_question, "question_text", "content", "question"),
                "student_answer": optional_text(raw_question, "student_answer", "answer_text"),
                "correct_answer": optional_text(raw_question, "correct_answer", "standard_answer", "answer"),
                "question_type": optional_text(raw_question, "question_type", "type"),
                "knowledge_point": required_text(raw_question, "knowledge_point", "knowledge"),
                **grade,
            }
        )

    total_score = as_float(
        first(payload, "total_score", default=sum(item["max_score"] for item in questions)),
        "total_score",
    )
    student_score = as_float(
        first(payload, "student_score", "score", default=sum(item["score"] for item in questions)),
        "student_score",
    )
    raw_weak_points = first(payload, "weak_points", default=None)
    if isinstance(raw_weak_points, list):
        weak_points = [str(item).strip() for item in raw_weak_points if str(item).strip()]
    else:
        weak_points = [
            item["knowledge_point"]
            for item in questions
            if not item["is_correct"] and item["knowledge_point"]
        ]
    weak_points = list(dict.fromkeys(weak_points))
    overall_comment = str(
        first(payload, "overall_comment", "comment", "summary", default=f"已完成 {len(questions)} 道题批改")
    ).strip()
    return ModelGradePayload.model_validate(
        {
            "subject": subject,
            "questions": questions,
            "total_score": total_score,
            "student_score": student_score,
            "overall_comment": overall_comment,
            "weak_points": weak_points,
        }
    )
