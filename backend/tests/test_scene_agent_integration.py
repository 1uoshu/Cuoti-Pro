import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from app.kernel.context import get_kernel_context, set_kernel_context
from app.main import app


class SceneLLM:
    async def vision_json_many_with_python(self, *_, **__):
        return {
            "subject": "数学",
            "questions": [
                {
                    "question_number": "1",
                    "question_text": "1 + 1 = ?",
                    "student_answer": "3",
                    "correct_answer": "2",
                    "knowledge_point": "整数加法",
                    "score": 0,
                    "max_score": 10,
                    "is_correct": False,
                    "explanation": "计算错误",
                    "confidence": 0.99,
                },
                {
                    "question_number": "2",
                    "question_text": "2 + 2 = ?",
                    "student_answer": "4",
                    "correct_answer": "4",
                    "knowledge_point": "整数加法",
                    "score": 10,
                    "max_score": 10,
                    "is_correct": True,
                    "explanation": "回答正确",
                    "confidence": 0.99,
                },
            ],
            "total_score": 20,
            "student_score": 10,
            "overall_comment": "需要巩固整数加法",
            "weak_points": ["整数加法"],
        }

    async def chat_json_with_python(self, _system_prompt, user_prompt, *_args, **kwargs):
        if kwargs["max_tokens"] == 3000:
            return {
                "questions": [
                    {
                        "content": "3 + 3 = ?",
                        "standard_answer": "6",
                        "explanation": "整数相加",
                        "knowledge_point": "整数加法",
                        "confidence": 0.99,
                    },
                    {
                        "content": "4 + 4 = ?",
                        "standard_answer": "8",
                        "explanation": "整数相加",
                        "knowledge_point": "整数加法",
                        "confidence": 0.99,
                    },
                ]
            }

        correct = "<student_answer>6</student_answer>" in user_prompt
        return {
            "is_correct": correct,
            "score": 4 if correct else 0,
            "max_score": 5 if correct else 10,
            "explanation": "回答正确" if correct else "答案不正确",
            "confidence": 0,
        }


class LowConfidenceLLM(SceneLLM):
    async def vision_json_many_with_python(self, *_, **__):
        return {
            "subject": "数学",
            "questions": [
                {
                    "question_number": "1",
                    "question_text": "识别不清的手写公式",
                    "student_answer": "?",
                    "correct_answer": "待确认",
                    "knowledge_point": "函数",
                    "score": 0,
                    "max_score": 10,
                    "is_correct": False,
                    "explanation": "图像识别置信度不足",
                    "confidence": 0,
                }
            ],
            "total_score": 10,
            "student_score": 0,
            "overall_comment": "图像识别置信度不足",
            "weak_points": ["函数"],
        }


class FailingLLM(SceneLLM):
    async def vision_json_many_with_python(self, *_, **__):
        raise RuntimeError("model secret and stack details")


def test_scene_one_and_two_complete_through_public_backend_apis():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=SceneLLM()))
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

            blank_question = client.put(
                f"/api/questions/{assignment['questions'][0]['id']}",
                headers=headers,
                json={"content": "   "},
            )
            assert blank_question.status_code == 422
            assert blank_question.json()["code"] == 4220

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

            blank_answer = client.post(
                f"/api/practices/{practice['id']}/submit",
                headers=headers,
                json={
                    "answers": [
                        {"question_id": practice["questions"][0]["id"], "answer": "   "},
                        {"question_id": practice["questions"][1]["id"], "answer": "0"},
                    ]
                },
            )
            assert blank_answer.status_code == 422

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
            assert result["questions"][0]["answers"][0]["confidence"] == 0
            assert result["questions"][0]["answers"][0]["confidence_warning"]

            duplicate = client.post(
                f"/api/practices/{practice['id']}/submit",
                headers=headers,
                json={
                    "answers": [
                        {"question_id": practice["questions"][0]["id"], "answer": "6"},
                        {"question_id": practice["questions"][1]["id"], "answer": "0"},
                    ]
                },
            )
            assert duplicate.status_code == 409
    finally:
        set_kernel_context(original_context)


def test_low_confidence_result_warns_user_without_blocking_learning_updates():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=LowConfidenceLLM()))
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


def test_failed_assignment_task_returns_safe_user_message():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=FailingLLM()))
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token = _register(client)
            headers = {"Authorization": f"Bearer {token}"}
            upload = client.post(
                "/api/assignments",
                headers=headers,
                data={"subject": "数学", "title": "失败提示测试"},
                files={"file": ("failed.png", b"failed-image", "image/png")},
            )
            assert upload.status_code == 200
            task_id = upload.json()["data"]["task"]["id"]

            task = client.get(f"/api/tasks/{task_id}", headers=headers).json()["data"]
            audit_logs = client.get("/api/audit-logs/me", headers=headers).json()["data"]
            failed_event = next(item for item in audit_logs if item["event_type"] == "assignment.grading.failed")

        assert task["status"] == "failed"
        assert task["error_message"] == "智能服务暂时不可用，请稍后重试"
        assert "secret" not in task["error_message"]
        assert failed_event["error_message"] == "智能服务暂时不可用，请稍后重试"
        assert "secret" not in failed_event["error_message"]
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
