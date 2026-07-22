import base64
from pathlib import Path
from typing import TypedDict

import fitz

from app.kernel.agent import AgentStep
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
        return {"image_data_urls": _load_upload_as_data_urls(state["file_path"])}

    async def grade_node(state: GradingState) -> GradingState:
        grade_label = state.get("grade") or ""
        subject = state["subject"]
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
