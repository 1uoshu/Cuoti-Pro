import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256

from fastapi.testclient import TestClient

from app.kernel.database import SessionLocal
from app.kernel.context import get_kernel_context, set_kernel_context
from app.main import app
from app.plugins.assignment_grading.models import Assignment, Question
from app.plugins.wrong_question_book.models import WrongQuestion


class ExamLLM:
    async def chat_json_with_python(self, _system_prompt, user_prompt, _sandbox, *, temperature, max_tokens):
        if max_tokens == 6000:
            assert temperature == 0.3
            return {
                "questions": [
                    {
                        "content": f"阶段评估题 {index}",
                        "standard_answer": f"答案 {index}",
                        "explanation": f"解析 {index}",
                        "knowledge_point": "导数定义" if index % 2 else "导数单调性",
                        "confidence": 0.99,
                    }
                    for index in range(1, 6)
                ]
            }
        assert temperature == 0.1
        assert max_tokens == 800
        is_correct = "<student_answer>正确</student_answer>" in user_prompt
        return {
            "is_correct": is_correct,
            "score": 10 if is_correct else 0,
            "max_score": 10,
            "explanation": "回答正确" if is_correct else "答案不正确",
            "confidence": 0.99,
        }


def test_weekly_report_aggregates_authenticated_students_questions():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now()

        with SessionLocal() as db:
            assignment = Assignment(
                user_id=user_id,
                title="函数周测",
                subject="数学",
                original_filename="weekly.png",
                file_path="storage/tests/weekly.png",
                status="completed",
                total_score=30,
                student_score=20,
                created_at=now,
                updated_at=now,
            )
            db.add(assignment)
            db.flush()
            questions = [
                Question(
                    assignment_id=assignment.id,
                    question_number=str(index),
                    content=f"题目 {index}",
                    score=10 if index < 3 else 0,
                    max_score=10,
                    is_correct=index < 3,
                    knowledge_point="导数",
                    explanation="回答正确" if index < 3 else "计算错误",
                    created_at=now,
                    updated_at=now,
                )
                for index in range(1, 4)
            ]
            db.add_all(questions)
            db.flush()
            db.add(
                WrongQuestion(
                    user_id=user_id,
                    question_id=questions[-1].id,
                    subject="数学",
                    knowledge_point="导数",
                    wrong_reason="计算错误",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()

        response = client.get(
            "/api/reports",
            headers=headers,
            params={"period": "周报", "subject": "数学"},
        )

    assert response.status_code == 200
    reports = response.json()["data"]
    assert len(reports) == 1
    report = reports[0]
    assert report["period"] == "周报"
    assert report["subject"] == "数学"
    assert report["stats"] == {
        "total_questions": 3,
        "correct_questions": 2,
        "error_questions": 1,
        "accuracy": 67,
    }
    assert len(report["trend"]["dates"]) == 7
    assert sum(report["trend"]["wrong_counts"]) == 1
    assert report["subject_distribution"] == [
        {"subject": "数学", "wrong_count": 1, "percent": 100}
    ]
    assert report["error_types"] == [{"type": "计算错误", "count": 1, "percent": 100}]


def test_student_can_create_list_and_read_an_exam():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=ExamLLM()))
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token, _ = _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}
            created_response = client.post(
                "/api/exams",
                headers=headers,
                json={
                    "subject": "数学",
                    "exam_type": "单元卷",
                    "knowledge_points": ["导数定义", "导数单调性"],
                    "difficulty": "混合难度",
                    "question_count": 5,
                },
            )

            assert created_response.status_code == 200
            created = created_response.json()["data"]
            assert created["title"] == "数学·阶段评估试卷"
            assert created["status"] == "ready"
            assert created["question_count"] == 5
            assert created["estimated_minutes"] == 10

            exams = client.get("/api/exams", headers=headers).json()["data"]
            detail = client.get(f"/api/exams/{created['id']}", headers=headers).json()["data"]

        assert [item["id"] for item in exams] == [created["id"]]
        assert len(detail["questions"]) == 5
        assert {item["knowledge_point"] for item in detail["questions"]} == {"导数定义", "导数单调性"}
    finally:
        set_kernel_context(original_context)


def test_student_can_submit_a_complete_exam_once_and_update_mastery():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=ExamLLM()))
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token, _ = _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}
            created = _create_exam(client, headers)
            detail = client.get(f"/api/exams/{created['id']}", headers=headers).json()["data"]
            answers = [
                {"question_id": question["id"], "answer": "正确" if index < 4 else "错误"}
                for index, question in enumerate(detail["questions"])
            ]

            submitted_response = client.post(
                f"/api/exams/{created['id']}/submit",
                headers=headers,
                json={"answers": answers},
            )
            duplicate_response = client.post(
                f"/api/exams/{created['id']}/submit",
                headers=headers,
                json={"answers": answers},
            )
            mastery = client.get("/api/mastery", headers=headers).json()["data"]

        assert submitted_response.status_code == 200, submitted_response.json()
        submitted = submitted_response.json()["data"]
        assert submitted["status"] == "completed"
        assert submitted["student_score"] == 80
        assert [item["answers"][0]["is_correct"] for item in submitted["questions"]] == [
            True,
            True,
            True,
            True,
            False,
        ]
        assert duplicate_response.status_code == 409
        by_point = {item["knowledge_point"]: item for item in mastery}
        assert by_point["导数定义"]["correct_count"] == 2
        assert by_point["导数定义"]["wrong_count"] == 1
        assert by_point["导数单调性"]["correct_count"] == 2
    finally:
        set_kernel_context(original_context)


def test_exam_score_compare_uses_the_two_latest_completed_exams():
    original_context = get_kernel_context()
    test_context = replace(original_context, capabilities=replace(original_context.capabilities, llm=ExamLLM()))
    set_kernel_context(test_context)
    try:
        with TestClient(app) as client:
            token, _ = _register_user(client)
            headers = {"Authorization": f"Bearer {token}"}
            first = _create_exam(client, headers)
            _submit_exam(client, headers, first["id"], correct_count=3)
            second = _create_exam(client, headers)
            _submit_exam(client, headers, second["id"], correct_count=4)

            response = client.get(
                "/api/exams/score-compare",
                headers=headers,
                params={"subject": "数学"},
            )

        assert response.status_code == 200
        comparison = response.json()["data"]
        assert comparison["last_score"] == 60
        assert comparison["current_score"] == 80
        assert comparison["improvement"] == 20
        by_point = {item["knowledge_point"]: item for item in comparison["mastery_changes"]}
        assert by_point["导数定义"] == {
            "knowledge_point": "导数定义",
            "previous": 67,
            "current": 67,
            "change": 0,
        }
        assert by_point["导数单调性"] == {
            "knowledge_point": "导数单调性",
            "previous": 50,
            "current": 100,
            "change": 50,
        }
    finally:
        set_kernel_context(original_context)


def _register_user(client: TestClient) -> tuple[str, int]:
    challenge = client.get("/api/auth/pow/challenge", params={"purpose": "register"}).json()["data"]
    nonce = 0
    prefix = "0" * int(challenge["difficulty"])
    while not sha256(f"{challenge['nonce_seed']}:{nonce}".encode()).hexdigest().startswith(prefix):
        nonce += 1
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"insights_{uuid.uuid4().hex[:12]}",
            "password": "password123",
            "nickname": "分析测试学生",
            "grade": "高三",
            "main_subject": "数学",
            "pow_challenge_id": challenge["challenge_id"],
            "pow_nonce": str(nonce),
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data["access_token"], data["user"]["id"]


def _create_exam(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/exams",
        headers=headers,
        json={
            "subject": "数学",
            "exam_type": "单元卷",
            "knowledge_points": ["导数定义", "导数单调性"],
            "difficulty": "混合难度",
            "question_count": 5,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def _submit_exam(client: TestClient, headers: dict[str, str], exam_id: int, *, correct_count: int) -> dict:
    detail = client.get(f"/api/exams/{exam_id}", headers=headers).json()["data"]
    response = client.post(
        f"/api/exams/{exam_id}/submit",
        headers=headers,
        json={
            "answers": [
                {"question_id": question["id"], "answer": "正确" if index < correct_count else "错误"}
                for index, question in enumerate(detail["questions"])
            ]
        },
    )
    assert response.status_code == 200, response.json()
    return response.json()["data"]


def test_tracking_overview_reports_weighted_mastery_today_count_and_streak():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now()

        with SessionLocal() as db:
            _seed_mastery(db, user_id, knowledge_point="导数", correct_count=8, wrong_count=2)
            _seed_mastery(db, user_id, knowledge_point="积分", correct_count=2, wrong_count=8)
            wrong = WrongQuestion(
                user_id=user_id,
                question_id=9001,
                subject="数学",
                knowledge_point="导数",
                wrong_reason="计算错误",
                status="unreviewed",
                created_at=now,
                updated_at=now,
            )
            db.add(wrong)
            assignment = Assignment(
                user_id=user_id,
                title="今日作业",
                subject="数学",
                original_filename="today.png",
                file_path="storage/tests/today.png",
                status="completed",
                created_at=now,
                updated_at=now,
            )
            db.add(assignment)
            db.commit()

        response = client.get("/api/tracking/overview", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["overall_mastery"] == 50
    assert data["today_review_count"] >= 1
    assert data["streak_days"] == 1


def test_knowledge_graph_groups_records_into_four_levels_and_sorts_weak_first():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}

        with SessionLocal() as db:
            _seed_mastery(db, user_id, knowledge_point="函数", correct_count=9, wrong_count=1)
            _seed_mastery(db, user_id, knowledge_point="数列", correct_count=7, wrong_count=3)
            _seed_mastery(db, user_id, knowledge_point="几何", correct_count=5, wrong_count=5)
            _seed_mastery(db, user_id, knowledge_point="概率", correct_count=1, wrong_count=9)
            db.commit()

        response = client.get("/api/knowledge-graph", headers=headers)

    assert response.status_code == 200
    nodes = response.json()["data"]["nodes"]
    by_name = {node["name"]: node for node in nodes}
    assert by_name["函数"]["level"] == 1
    assert by_name["数列"]["level"] == 2
    assert by_name["几何"]["level"] == 3
    assert by_name["概率"]["level"] == 4
    levels = [node["level"] for node in nodes]
    assert levels == sorted(levels, key=lambda value: (-value, node_mastery(by_name, value)))


def test_review_schedule_uses_today_as_active_bucket():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now()

        with SessionLocal() as db:
            for offset in (0, 1, 5, 6, 7, 15):
                created = now - timedelta(days=offset)
                db.add(
                    WrongQuestion(
                        user_id=user_id,
                        question_id=10_000 + offset,
                        subject="数学",
                        knowledge_point="导数",
                        wrong_reason="计算错误",
                        status="unreviewed",
                        created_at=created,
                        updated_at=created,
                    )
                )
            db.commit()

        response = client.get("/api/tracking/review-schedule", headers=headers)

    assert response.status_code == 200
    schedule = response.json()["data"]
    assert [item["stage"] for item in schedule] == ["今天", "7天后", "14天后", "30天后"]
    active = [item for item in schedule if item["active"]]
    assert len(active) == 1 and active[0]["stage"] == "今天"
    counts = {item["stage"]: item["question_count"] for item in schedule}
    assert counts["今天"] == 2
    assert counts["7天后"] == 3


def test_activity_heatmap_aggregates_assignment_practice_and_exam_by_day():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        with SessionLocal() as db:
            assignment = Assignment(
                user_id=user_id,
                title="今日数学",
                subject="数学",
                original_filename="today.png",
                file_path="storage/tests/today.png",
                status="completed",
                created_at=today,
                updated_at=today,
            )
            db.add(assignment)
            db.flush()
            db.add(
                Question(
                    assignment_id=assignment.id,
                    question_number="1",
                    content="题目",
                    created_at=today,
                    updated_at=today,
                )
            )
            db.add(
                Question(
                    assignment_id=assignment.id,
                    question_number="2",
                    content="题目",
                    created_at=today,
                    updated_at=today,
                )
            )
            db.add(
                Question(
                    assignment_id=assignment.id,
                    question_number="3",
                    content="题目",
                    created_at=today,
                    updated_at=today,
                )
            )
            db.add(
                WrongQuestion(
                    user_id=user_id,
                    question_id=8001,
                    subject="数学",
                    knowledge_point="导数",
                    wrong_reason="计算错误",
                    created_at=yesterday,
                    updated_at=yesterday,
                )
            )
            db.commit()

        response = client.get("/api/tracking/activity-heatmap", headers=headers)

    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 14
    today_label = f"{today.month}/{today.day}"
    today_row = next(row for row in rows if row["date"] == today_label)
    assert today_row["question_count"] == 3
    assert today_row["level"] == 2
    yesterday_row = next(row for row in rows if row["date"] == f"{yesterday.month}/{yesterday.day}")
    assert yesterday_row["question_count"] == 0
    assert yesterday_row["level"] == 0


def _seed_mastery(db, user_id: int, *, knowledge_point: str, correct_count: int, wrong_count: int):
    record = MasteryRecord(
        user_id=user_id,
        subject="数学",
        knowledge_point=knowledge_point,
        correct_count=correct_count,
        wrong_count=wrong_count,
    )
    total = correct_count + wrong_count
    record.mastery_score = round(correct_count / total * 100, 1) if total else 0
    db.add(record)


def node_mastery(by_name: dict, level: int) -> float:
    for node in by_name.values():
        if node["level"] == level:
            return node["mastery_score"]
    return 0.0
from app.plugins.mastery_tracking.models import MasteryRecord


def test_profile_stats_aggregates_wrongs_mastery_and_streak():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now()

        with SessionLocal() as db:
            _seed_mastery(db, user_id, knowledge_point="导数", correct_count=9, wrong_count=1)
            _seed_mastery(db, user_id, knowledge_point="积分", correct_count=1, wrong_count=9)
            _seed_mastery(db, user_id, knowledge_point="数列", correct_count=2, wrong_count=8)
            for offset in range(3):
                db.add(
                    WrongQuestion(
                        user_id=user_id,
                        question_id=20_000 + offset,
                        subject="数学",
                        knowledge_point="导数",
                        wrong_reason="计算错误",
                        created_at=now,
                        updated_at=now,
                    )
                )
            assignment = Assignment(
                user_id=user_id,
                title="今日作业",
                subject="数学",
                original_filename="today.png",
                file_path="storage/tests/today.png",
                status="completed",
                created_at=now,
                updated_at=now,
            )
            db.add(assignment)
            db.commit()

        response = client.get("/api/profile/stats", headers=headers)

    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats == {
        "total_errors": 3,
        "mastered_points": 1,
        "weak_points": 2,
        "continuous_days": 1,
    }


def test_profile_preferences_default_when_unset_and_persisted_after_put():
    with TestClient(app) as client:
        token, _ = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}

        defaults = client.get("/api/profile/preferences", headers=headers).json()["data"]
        assert defaults == {
            "daily_goal": 20,
            "review_time": "19:30",
            "difficulty": "adaptive",
            "weak_reminder": True,
        }

        response = client.put(
            "/api/profile/preferences",
            headers=headers,
            json={
                "daily_goal": 30,
                "review_time": "07:15",
                "difficulty": "variation",
                "weak_reminder": False,
            },
        )
        assert response.status_code == 200, response.json()
        updated = response.json()["data"]
        assert updated == {
            "daily_goal": 30,
            "review_time": "07:15",
            "difficulty": "variation",
            "weak_reminder": False,
        }

        reread = client.get("/api/profile/preferences", headers=headers).json()["data"]
        assert reread == updated


def test_profile_preferences_put_rejects_invalid_values():
    with TestClient(app) as client:
        token, _ = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}

        invalid_goal = client.put("/api/profile/preferences", headers=headers, json={"daily_goal": 12})
        assert invalid_goal.status_code == 422

        invalid_time = client.put("/api/profile/preferences", headers=headers, json={"review_time": "25:00"})
        assert invalid_time.status_code == 422

        invalid_difficulty = client.put("/api/profile/preferences", headers=headers, json={"difficulty": "lol"})
        assert invalid_difficulty.status_code == 422


def test_wrong_questions_include_question_created_at():
    with TestClient(app) as client:
        token, user_id = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now()

        with SessionLocal() as db:
            assignment = Assignment(
                user_id=user_id,
                title="数学作业",
                subject="数学",
                original_filename="hw.png",
                file_path="storage/tests/hw.png",
                status="completed",
                created_at=now,
                updated_at=now,
            )
            db.add(assignment)
            db.flush()
            question = Question(
                assignment_id=assignment.id,
                question_number="1",
                content="题目",
                created_at=now,
                updated_at=now,
            )
            db.add(question)
            db.flush()
            db.add(
                WrongQuestion(
                    user_id=user_id,
                    question_id=question.id,
                    subject="数学",
                    knowledge_point="导数",
                    wrong_reason="计算错误",
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()

        response = client.get("/api/wrong-questions", headers=headers)

    assert response.status_code == 200
    items = response.json()["data"]
    assert len(items) == 1
    assert items[0]["question"]["created_at"] is not None
