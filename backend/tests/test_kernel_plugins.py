import uuid
from hashlib import sha256

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


def test_unknown_route_and_method_errors_use_api_envelope():
    with TestClient(app) as client:
        not_found = client.get("/api/does-not-exist")
        method_not_allowed = client.put("/api/example/ping")

    assert not_found.status_code == 404
    assert not_found.json()["code"] == 404
    assert "detail" not in not_found.json()
    assert method_not_allowed.status_code == 405
    assert method_not_allowed.json()["code"] == 405
    assert "detail" not in method_not_allowed.json()


def test_duplicate_registration_returns_conflict():
    with TestClient(app) as client:
        username = f"duplicate_{uuid.uuid4().hex[:12]}"
        payload = {
            "username": username,
            "password": "password123",
            "nickname": "测试学生",
        }
        assert register_with_pow(client, payload).status_code == 200
        response = register_with_pow(client, payload)

    assert response.status_code == 409
    assert response.json()["code"] == 409


def test_assignment_subject_length_is_rejected_before_persistence():
    with TestClient(app) as client:
        token = _register_user(client)
        response = client.post(
            "/api/assignments",
            headers={"Authorization": f"Bearer {token}"},
            data={"subject": "x" * 33},
            files={"file": ("homework.png", b"image", "image/png")},
        )

    assert response.status_code == 400
    assert response.json()["code"] == 400


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

        for path in ["/api/dashboard", "/api/mastery", "/api/wrong-questions", "/api/assignments"]:
            response = client.get(path, headers=headers)

            assert response.status_code == 200
            assert response.json()["code"] == 0


def test_registration_is_audited_without_exposing_logs_to_students():
    with TestClient(app) as client:
        token = _register_user(client)
        response = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def _register_user(client: TestClient) -> str:
    username = f"student_{uuid.uuid4().hex[:12]}"
    response = register_with_pow(
        client,
        {
            "username": username,
            "password": "password123",
            "nickname": "测试学生",
            "grade": "高三",
            "main_subject": "数学",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def register_with_pow(client: TestClient, payload: dict[str, str]) -> object:
    challenge = client.get("/api/auth/pow/challenge", params={"purpose": "register"}).json()["data"]
    payload = {**payload, "pow_challenge_id": challenge["challenge_id"], "pow_nonce": solve_pow(challenge)}
    return client.post("/api/auth/register", json=payload)


def solve_pow(challenge: dict[str, object]) -> str:
    difficulty = int(challenge["difficulty"])
    nonce_seed = str(challenge["nonce_seed"])
    nonce = 0
    prefix = "0" * difficulty
    while True:
        candidate = str(nonce)
        if sha256(f"{nonce_seed}:{candidate}".encode()).hexdigest().startswith(prefix):
            return candidate
        nonce += 1
