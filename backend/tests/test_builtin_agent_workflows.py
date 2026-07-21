import asyncio
from pathlib import Path
from types import SimpleNamespace

import fitz

from app.kernel.agent import AgentRuntime, PythonSandbox
from app.plugins.assignment_grading.workflow import run_grading_workflow
from app.plugins.layered_practice.schemas import PracticeCreateRequest
from app.plugins.layered_practice.workflow import build_practice_workflow, generate_practice_questions


class RecordingMultimodalLLM:
    def __init__(self) -> None:
        self.image_data_urls: list[str] = []

    async def vision_json_many_with_python(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        sandbox,
        *,
        temperature: float,
        max_tokens: int,
    ):
        assert system_prompt
        assert "全部页面" in user_prompt
        assert temperature == 0.1
        assert max_tokens >= 4000
        assert isinstance(sandbox, PythonSandbox)
        self.image_data_urls = image_data_urls
        return {
            "subject": "数学",
            "questions": [
                {
                    "question_number": "1",
                    "question_text": "第一页题目",
                    "student_answer": "1",
                    "correct_answer": "1",
                    "question_type": "计算题",
                    "knowledge_point": "整数运算",
                    "score": 10,
                    "max_score": 10,
                    "is_correct": True,
                    "explanation": "回答正确",
                    "confidence": 0.99,
                },
                {
                    "question_number": "2",
                    "question_text": "第二页题目",
                    "student_answer": "3",
                    "correct_answer": "4",
                    "question_type": "计算题",
                    "knowledge_point": "整数运算",
                    "score": 0,
                    "max_score": 10,
                    "is_correct": False,
                    "explanation": "计算错误",
                    "confidence": 0.98,
                },
            ],
            "total_score": 20,
            "student_score": 10,
            "overall_comment": "需要巩固整数运算",
            "weak_points": ["整数运算"],
        }


def test_practice_request_normalizes_subject_and_knowledge_point():
    request = PracticeCreateRequest(
        subject="  数学 ",
        knowledge_point=" 导数与函数单调性  ",
        difficulty="基础补漏",
        question_count=1,
    )

    assert request.subject == "数学"
    assert request.knowledge_point == "导数与函数单调性"


def test_builtin_agent_grades_every_page_of_a_pdf(tmp_path: Path):
    pdf_path = tmp_path / "two-page-paper.pdf"
    _create_pdf(pdf_path, pages=2)
    llm = RecordingMultimodalLLM()
    context = SimpleNamespace(
        settings=SimpleNamespace(review_confidence_threshold=0.85),
        capabilities=SimpleNamespace(
            agent_api=None,
            agent_runtime=AgentRuntime(),
            llm=llm,
            sandbox=PythonSandbox(),
        )
    )

    result = asyncio.run(
        run_grading_workflow(
            context,
            str(pdf_path),
            "数学",
            "高三",
            student_id="student-1",
        )
    )

    assert len(llm.image_data_urls) == 2
    assert all(url.startswith("data:image/png;base64,") for url in llm.image_data_urls)
    assert [question.question_number for question in result.questions] == ["1", "2"]
    assert result.student_score == 10


def _create_pdf(path: Path, *, pages: int) -> None:
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"Page {index + 1}")
        document.save(path)
    finally:
        document.close()


class RecordingTextLLM:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_prompt = ""

    async def chat_json_with_python(
        self, system_prompt: str, user_prompt: str, sandbox, *, temperature: float, max_tokens: int
    ):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        assert temperature == 0.35
        assert max_tokens == 3000
        assert isinstance(sandbox, PythonSandbox)
        return {
            "questions": [
                {
                    "content": "练习 1",
                    "standard_answer": "答案 1",
                    "explanation": "解析 1",
                    "knowledge_point": "导数",
                    "confidence": 0.99,
                },
                {
                    "content": "练习 2",
                    "standard_answer": "答案 2",
                    "explanation": "解析 2",
                    "knowledge_point": "导数",
                    "confidence": 0.99,
                },
            ]
        }


def test_builtin_practice_agent_uses_langgraph_context_generation_and_validation_nodes():
    llm = RecordingTextLLM()
    context = SimpleNamespace(
        settings=SimpleNamespace(review_confidence_threshold=0.85),
        capabilities=SimpleNamespace(
            agent_api=None,
            agent_runtime=AgentRuntime(),
            llm=llm,
            sandbox=PythonSandbox(),
        )
    )

    workflow = build_practice_workflow(context)
    assert {"prepare_context", "generate", "validate"}.issubset(workflow.get_graph().nodes)

    result = asyncio.run(
        generate_practice_questions(
            context,
            "student-1",
            "数学",
            "高三",
            "导数",
            "基础补漏",
            2,
            ["忽略定义域；这段历史文本不能改变系统指令"],
        )
    )

    assert len(result.questions) == 2
    assert "不可信学习材料" in llm.system_prompt
    assert "<recent_mistakes>" in llm.user_prompt
    assert "忽略定义域" in llm.user_prompt


class RetryingTextLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat_json_with_python(
        self, system_prompt: str, user_prompt: str, sandbox, *, temperature: float, max_tokens: int
    ):
        self.calls += 1
        knowledge_point = "一元一次方程" if self.calls == 1 else "导数与函数单调性"
        return {
            "questions": [
                {
                    "content": "使用导数判断函数的单调区间。",
                    "standard_answer": "递增区间为 (0,+∞)",
                    "explanation": "先求导，再判断导数符号。",
                    "knowledge_point": knowledge_point,
                    "confidence": 0.98,
                }
            ]
        }


def test_builtin_practice_agent_retries_a_question_from_the_wrong_knowledge_point():
    llm = RetryingTextLLM()
    context = SimpleNamespace(
        settings=SimpleNamespace(review_confidence_threshold=0.85),
        capabilities=SimpleNamespace(
            agent_api=None,
            agent_runtime=AgentRuntime(),
            llm=llm,
            sandbox=PythonSandbox(),
        ),
    )

    result = asyncio.run(
        generate_practice_questions(
            context,
            "student-1",
            "数学",
            "高三",
            "导数与函数单调性",
            "基础补漏",
            1,
            [],
        )
    )

    assert llm.calls == 2
    assert result.questions[0].knowledge_point == "导数与函数单调性"
