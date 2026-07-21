import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from app.kernel.context import get_kernel_context, set_kernel_context
from app.main import app


class SceneAgentAPI:
    async def grade_file(self, **_):
        return {
            "questions": [
                {
                    "number": "1",
                    "question": "1 + 1 = ?",
                    "student_answer": "3",
                    "answer": "2",
                    "knowledge_point": "整数加法",
                    "score": 0,
                    "max_score": 10,
                    "correct": False,
                    "reason": "计算错误",
                    "confidence": 0.99,
                },
                {
                    "number": "2",
                    "question": "2 + 2 = ?",
                    "student_answer": "4",
                    "answer": "4",
                    "knowledge_point": "整数加法",
                    "score": 10,
                    "max_score": 10,
                    "correct": True,
                    "reason": "回答正确",
                    "confidence": 0.99,
                },
            ]
        }

    async def generate_practice(self, **_):
        return {
            "questions": [
                {"question": "3 + 3 = ?", "answer": "6", "analysis": "整数相加"},
                {"question": "4 + 4 = ?", "answer": "8", "analysis": "整数相加"},
            ]
        }

    async def answer_practice(self, **kwargs):
        correct = kwargs["student_answer"] == kwargs["question"]["standard_answer"]
        return {
            "correct": correct,
            "score": 4 if correct else 0,
            "max_score": 5 if correct else 10,
            "reason": "回答正确" if correct else "答案不正确",
        }


class LowConfidenceAgentAPI(SceneAgentAPI):
    async def grade_file(self, **_):
        return {
            "questions": [
                {
                    "number": "1",
                    "question": "识别不清的手写公式",
                    "student_answer": "?",
                    "answer": "待确认",
                    "knowledge_point": "函数",
                    "score": 0,
                    "max_score": 10,
                    "correct": False,
                    "reason": "图像识别置信度不足",
                }
            ]
        }


def test_scene_one_and_two_complete_through_public_backend_apis():
    original_context = get_kernel_context()
    test_context = replace(
        original_context,
        capabilities=replace(original_context.capabilities, agent_api=SceneAgentAPI()),
    )
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token = _register(client)
            headers = {"Authorization": f"Bearer {token}"}

            upload = client.post(
                "/api/assignments",
                headers=headers,
                data={"subject": "数学", "title": "Agent 联调作业"},
                files={"file": ("homework.png", b"image-content", "image/png")},
            )
            assert upload.status_code == 200
            assignment_id = upload.json()["data"]["assignment_id"]
            task_id = upload.json()["data"]["task"]["id"]

            task = client.get(f"/api/tasks/{task_id}", headers=headers).json()["data"]
            assignment = client.get(f"/api/assignments/{assignment_id}", headers=headers).json()["data"]
            wrong_questions = client.get("/api/wrong-questions", headers=headers).json()["data"]
            mastery = client.get("/api/mastery", headers=headers).json()["data"]

            assert task["status"] == "completed", task["error_message"]
            assert assignment["student_score"] == 10
            assert len(assignment["questions"]) == 2
            assert len(wrong_questions) == 1
            assert wrong_questions[0]["wrong_reason"] == "计算错误"
            integer_addition = next(item for item in mastery if item["knowledge_point"] == "整数加法")
            assert integer_addition["correct_count"] == 1
            assert integer_addition["wrong_count"] == 1

            practice_response = client.post(
                "/api/practices",
                headers=headers,
                json={
                    "subject": "数学",
                    "knowledge_point": "整数加法",
                    "difficulty": "同类变式",
                    "question_count": 2,
                },
            )
            assert practice_response.status_code == 200
            practice = practice_response.json()["data"]
            assert practice["status"] == "ready"

            submitted = client.post(
                f"/api/practices/{practice['id']}/submit",
                headers=headers,
                json={
                    "answers": [
                        {"question_id": practice["questions"][0]["id"], "answer": "6"},
                        {"question_id": practice["questions"][1]["id"], "answer": "0"},
                    ]
                },
            )
            assert submitted.status_code == 200
            result = submitted.json()["data"]
            assert result["status"] == "completed"
            assert result["student_score"] == 40
            assert [item["answers"][0]["is_correct"] for item in result["questions"]] == [True, False]
    finally:
        set_kernel_context(original_context)


def test_low_confidence_result_warns_user_without_blocking_learning_updates():
    original_context = get_kernel_context()
    test_context = replace(
        original_context,
        capabilities=replace(original_context.capabilities, agent_api=LowConfidenceAgentAPI()),
    )
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token = _register(client)
            headers = {"Authorization": f"Bearer {token}"}
            upload = client.post(
                "/api/assignments",
                headers=headers,
                data={"subject": "数学", "title": "低置信度作业"},
                files={"file": ("unclear.png", b"unclear-image", "image/png")},
            )
            assignment_id = upload.json()["data"]["assignment_id"]

            assignment = client.get(f"/api/assignments/{assignment_id}", headers=headers).json()["data"]
            wrong_questions = client.get("/api/wrong-questions", headers=headers).json()["data"]
            mastery = client.get("/api/mastery", headers=headers).json()["data"]

            assert assignment["status"] == "completed"
            assert assignment["questions"][0]["confidence"] == 0
            assert assignment["questions"][0]["needs_review"] is True
            assert assignment["questions"][0]["confidence_warning"]
            assert len(wrong_questions) == 1
            assert len(mastery) == 1
    finally:
        set_kernel_context(original_context)


def _register(client: TestClient) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"agent_scene_{uuid.uuid4().hex[:12]}",
            "password": "password123",
            "nickname": "Agent 场景学生",
            "grade": "高三",
            "main_subject": "数学",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]
