import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.kernel.agent import AgentRuntime
from app.plugins.assignment_grading.workflow import regrade_text_question, run_grading_workflow
from app.plugins.layered_practice.workflow import generate_practice_questions, grade_practice_answer


class FakeAgentAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def grade_file(self, **kwargs):
        self.calls.append(("grade_file", kwargs))
        return {
            "questions": [
                {
                    "question_number": "1",
                    "content": "求 1+1",
                    "student_answer": "3",
                    "correct_answer": "2",
                    "type": "计算题",
                    "knowledge_point": "整数加法",
                    "score": 0,
                    "max_score": 10,
                    "is_correct": False,
                    "analysis": "计算错误",
                }
            ],
            "comment": "注意基础计算",
        }

    async def grade_text(self, **kwargs):
        self.calls.append(("grade_text", kwargs))
        return {"correct": True, "score": 10, "feedback": "回答正确"}

    async def generate_practice(self, **kwargs):
        self.calls.append(("generate_practice", kwargs))
        return {
            "questions": [
                {"question": "题目 A", "answer": "答案 A", "analysis": "解析 A"},
                {"content": "题目 B", "standard_answer": "答案 B", "explanation": "解析 B"},
            ]
        }

    async def answer_practice(self, **kwargs):
        self.calls.append(("answer_practice", kwargs))
        return {"is_correct": False, "score": 2, "reason": "符号错误"}


class FailingLLM:
    async def chat_json(self, *args, **kwargs):
        raise AssertionError("Agent API path must not call the model gateway")

    async def vision_json(self, *args, **kwargs):
        raise AssertionError("Agent API path must not call the model gateway")


def _context(agent_api: FakeAgentAPI):
    return SimpleNamespace(
        capabilities=SimpleNamespace(
            agent_api=agent_api,
            agent_runtime=AgentRuntime(),
            llm=FailingLLM(),
        )
    )


def test_scene_one_grading_uses_agent_pdf_api_and_normalizes_result(tmp_path: Path):
    pdf_path = tmp_path / "试卷.pdf"
    pdf_path.write_bytes(b"%PDF-document")
    agent_api = FakeAgentAPI()

    result = asyncio.run(
        run_grading_workflow(
            _context(agent_api),
            str(pdf_path),
            "数学",
            "高三",
            student_id="42",
        )
    )

    method, request = agent_api.calls[0]
    assert method == "grade_file"
    assert request["student_id"] == "42"
    assert request["file_path"] == pdf_path
    assert "高三数学" in request["question"]
    assert result.subject == "数学"
    assert result.total_score == 10
    assert result.student_score == 0
    assert result.questions[0].question_text == "求 1+1"
    assert result.questions[0].explanation == "计算错误"
    assert result.questions[0].confidence == 0
    assert result.weak_points == ["整数加法"]


def test_scene_one_agent_grading_requires_a_knowledge_point(tmp_path: Path):
    class MissingKnowledgeAgent(FakeAgentAPI):
        async def grade_file(self, **kwargs):
            payload = await super().grade_file(**kwargs)
            payload["questions"][0].pop("knowledge_point")
            return payload

    image_path = tmp_path / "answer.png"
    image_path.write_bytes(b"image")

    with pytest.raises(ValueError, match="knowledge_point"):
        asyncio.run(
            run_grading_workflow(
                _context(MissingKnowledgeAgent()),
                str(image_path),
                "数学",
                "高三",
                student_id="42",
            )
        )


def test_scene_one_text_regrade_uses_agent_grade_endpoint():
    agent_api = FakeAgentAPI()

    result = asyncio.run(
        regrade_text_question(
            _context(agent_api),
            "数学",
            "1+1=?",
            "2",
            "2",
            student_id="7",
        )
    )

    assert agent_api.calls[0] == (
        "grade_text",
        {"student_id": "7", "question": "1+1=?\n参考答案：2", "student_answer": "2", "subject": "数学"},
    )
    assert result == {
        "is_correct": True,
        "score": 10.0,
        "max_score": 10.0,
        "explanation": "回答正确",
        "confidence": 0,
    }


def test_scene_two_generation_maps_difficulty_and_normalizes_questions():
    agent_api = FakeAgentAPI()

    result = asyncio.run(
        generate_practice_questions(
            _context(agent_api),
            "student-8",
            "数学",
            "高三",
            "导数",
            "同类变式",
            2,
            ["求导符号错误"],
        )
    )

    assert agent_api.calls[0] == (
        "generate_practice",
        {"student_id": "student-8", "weak_points": "导数", "difficulty": "variant"},
    )
    assert [item.content for item in result.questions] == ["题目 A", "题目 B"]
    assert result.questions[0].standard_answer == "答案 A"


def test_scene_two_generation_collects_single_question_agent_responses():
    class SingleQuestionAgent(FakeAgentAPI):
        async def generate_practice(self, **kwargs):
            self.calls.append(("generate_practice", kwargs))
            number = len(self.calls)
            return {
                "questions": [
                    {"question": f"题目 {number}", "answer": f"答案 {number}", "analysis": f"解析 {number}"}
                ]
            }

    agent_api = SingleQuestionAgent()

    result = asyncio.run(
        generate_practice_questions(
            _context(agent_api),
            "student-8",
            "数学",
            "高三",
            "导数",
            "基础补漏",
            3,
            [],
        )
    )

    assert len(agent_api.calls) == 3
    assert [item.content for item in result.questions] == ["题目 1", "题目 2", "题目 3"]


def test_scene_two_answer_uses_practice_answer_endpoint():
    agent_api = FakeAgentAPI()
    question = {"content": "题目 A", "standard_answer": "答案 A"}

    result = asyncio.run(grade_practice_answer(_context(agent_api), "student-8", "数学", question, "错误答案"))

    assert agent_api.calls[0] == (
        "answer_practice",
        {"student_id": "student-8", "question": question, "student_answer": "错误答案"},
    )
    assert result == {
        "is_correct": False,
        "score": 2.0,
        "max_score": 10.0,
        "explanation": "符号错误",
        "confidence": 0,
    }
