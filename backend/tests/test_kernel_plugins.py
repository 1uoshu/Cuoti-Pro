import uuid

from fastapi.testclient import TestClient

from app.main import app


def test_app_loads_configured_plugins():
    plugin_names = [plugin["name"] for plugin in app.state.plugin_manager.describe()]

    assert plugin_names == [
        "example",
        "mastery_tracking",
        "wrong_question_book",
        "assignment_grading",
        "layered_practice",
        "learning_dashboard",
    ]


def test_plugin_registry_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/plugins")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"][0]["name"] == "example"
    assert "assignment_grading" in {plugin["name"] for plugin in body["data"]}


def test_example_plugin_ping_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/example/ping")

    assert response.status_code == 200
    assert response.json()["data"] == {"plugin": "example", "status": "ok"}


def test_http_errors_use_api_envelope():
    with TestClient(app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 401
    assert body["message"]
    assert "detail" not in body


def test_validation_errors_use_api_envelope():
    with TestClient(app) as client:
        response = client.post("/api/auth/register", json={"username": "x"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 4220
    assert body["message"] == "请求参数校验失败"
    assert "errors" in body["data"]


def test_profile_update_rejects_null_nickname_at_validation_boundary():
    with TestClient(app) as client:
        token = _register_user(client)
        response = client.put(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": None},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 4220
    assert any(error["loc"][-1] == "nickname" for error in body["data"]["errors"])


def test_authenticated_scene_read_endpoints_return_envelopes():
    with TestClient(app) as client:
        token = _register_user(client)
        headers = {"Authorization": f"Bearer {token}"}

        for path in ["/api/dashboard", "/api/mastery", "/api/wrong-questions", "/api/assignments", "/api/audit-logs/me"]:
            response = client.get(path, headers=headers)

            assert response.status_code == 200
            assert response.json()["code"] == 0


def test_registration_is_audited():
    with TestClient(app) as client:
        token = _register_user(client)
        response = client.get("/api/audit-logs/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    events = response.json()["data"]
    assert events
    assert events[0]["event_type"] == "auth.register"
    assert events[0]["resource_type"] == "user"
    assert "password" not in events[0]["metadata"]


def _register_user(client: TestClient) -> str:
    username = f"student_{uuid.uuid4().hex[:12]}"
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "password123",
            "nickname": "测试学生",
            "grade": "高三",
            "main_subject": "数学",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]
