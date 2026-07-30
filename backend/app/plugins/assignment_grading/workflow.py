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
    _ocr_text: str
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
            # PDF 页面渲染成 PNG（无损）：作业多为手写公式，JPEG 有损压缩会伤害 OCR 识别。
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append(f"data:image/png;base64,{encoded}")
        return pages
    finally:
        document.close()


def _format_ocr_questions(questions: object) -> str:
    """把视觉模型返回的结构化题目列表拼成干净的判分输入文本。"""
    if not isinstance(questions, list) or not questions:
        return ""
    blocks: list[str] = []
    for index, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            continue
        number = str(item.get("question_number") or index).strip()
        text = str(item.get("question_text") or "").strip()
        if not text:
            continue
        options = str(item.get("options") or "").strip()
        student = str(item.get("student_answer") or "").strip() or "未作答"
        lines = [f"题号: {number}", f"题目: {text}"]
        if options and options not in {"无", "None"}:
            lines.append(f"选项: {options}")
        lines.append(f"学生答案: {student}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def build_grading_workflow(context: KernelContext):
    async def load_node(state: GradingState) -> GradingState:
        return {"image_data_urls": _load_upload_as_data_urls(state["file_path"])}

    async def ocr_node(state: GradingState) -> GradingState:
        """Step 1: 视觉识别 — Qwen3-VL 结构化提取（只识别不解题）。

        用严格 JSON 约束视觉模型，避免它自由发挥、越权解题、自相矛盾，
        再拼成干净文本交给 DeepSeek 判分。
        """
        subject = state["subject"]
        ocr_system = (
            "你是精确的作业识别助手，只负责逐字识别图片中真实存在的题目，绝不解题、不判分、"
            "不推断或编造图片中没有的题目、选项或答案。只输出有效 JSON。"
        )
        ocr_prompt = (
            f"识别这份{subject}作业图片。图片里有几道题就返回几道，不要编造多余题目，也不要遗漏。\n"
            "严禁解题、严禁计算、严禁给出或推断参考答案——你只做文字识别。\n"
            "只返回 JSON，结构如下：\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "question_number": "图片中的题号",\n'
            '      "question_text": "题干原文，数学公式用 LaTeX",\n'
            '      "options": "选择题就逐字列出各选项，如 A. 1  B. 2  C. 3  D. 4；非选择题填空字符串",\n'
            '      "student_answer": "学生手写/圈选的作答；看不清或没作答填 未作答"\n'
            "    }\n"
            "  ]\n"
            "}"
        )
        try:
            data = await context.capabilities.llm.vision_json_many(
                ocr_system,
                ocr_prompt,
                state["image_data_urls"],
                temperature=0.0,
                max_tokens=8000,
            )
            questions = data.get("questions") if isinstance(data, dict) else None
            ocr_text = _format_ocr_questions(questions)
        except Exception:
            ocr_text = ""
        if not ocr_text:
            # 结构化识别失败时回退到纯文本识别，保证链路不断
            ocr_text = await context.capabilities.llm.vision_ocr(
                system_prompt=ocr_system,
                user_prompt=(
                    f"逐题识别这份{subject}作业，每题按\n题号:\n题目:\n选项:\n学生答案:\n"
                    "格式输出。只识别真实存在的题目，不要解题、不要编造参考答案。"
                ),
                image_data_urls=state["image_data_urls"],
                temperature=0.0,
                max_tokens=8000,
            )
        return {"_ocr_text": ocr_text}

    async def grade_node(state: GradingState) -> GradingState:
        """Step 2: 推理判分 — DeepSeek 读取 OCR 文本，调用 python_verify 验算"""
        grade_label = state.get("grade") or ""
        subject = state["subject"]
        ocr_text = state.get("_ocr_text", "")
        grading_prompt = build_assignment_grading_prompt(grade=grade_label, subject=subject)
        full_prompt = f"{grading_prompt}\n\n以下是从作业图片中识别出的内容（只批改这里真实出现的题目）：\n\n{ocr_text}"
        data = await context.capabilities.llm.chat_json_with_python(
            GRADING_SYSTEM_PROMPT,
            full_prompt,
            context.capabilities.sandbox,
            temperature=0.1,
            max_tokens=8000,
            max_tool_calls=6,
        )
        return {"result": ModelGradePayload.model_validate(data)}

    return context.capabilities.agent_runtime.compile_linear_workflow(
        GradingState,
        [
            AgentStep("load", load_node),
            AgentStep("ocr", ocr_node),
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
