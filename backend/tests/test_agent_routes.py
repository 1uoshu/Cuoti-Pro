"""Integration tests for Agent HTTP routes — sessions, messages, upload, suggestions."""
import uuid
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ── Module-scoped client (lifespan runs only once) ───────────────────


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Helpers ──────────────────────────────────────────────────────────


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


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client: TestClient, token: str, title: str = "测试会话") -> dict:
    """Helper: create a session and return the response JSON data."""
    response = client.post(
        "/api/agent/sessions",
        headers=_auth_header(token),
        params={"title": title},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    return response.json()["data"]


# ── Session CRUD ─────────────────────────────────────────────────────


def test_create_session(client: TestClient):
    token = _register_user(client)
    response = client.post(
        "/api/agent/sessions",
        headers=_auth_header(token),
        params={"title": "测试会话"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert "id" in body["data"]
    assert body["data"]["title"] == "测试会话"


def test_list_sessions_empty(client: TestClient):
    token = _register_user(client)
    response = client.get("/api/agent/sessions", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == []


def test_list_sessions_returns_created(client: TestClient):
    token = _register_user(client)
    _create_session(client, token, title="我的会话")
    response = client.get("/api/agent/sessions", headers=_auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "我的会话"


def test_rename_session(client: TestClient):
    token = _register_user(client)
    session = _create_session(client, token, title="原标题")
    session_id = session["id"]

    response = client.patch(
        f"/api/agent/sessions/{session_id}",
        headers=_auth_header(token),
        data={"title": "新标题"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["title"] == "新标题"


def test_rename_session_not_found(client: TestClient):
    token = _register_user(client)
    response = client.patch(
        "/api/agent/sessions/999999",
        headers=_auth_header(token),
        data={"title": "不存在"},
    )

    assert response.status_code == 404


def test_delete_session(client: TestClient):
    token = _register_user(client)
    session = _create_session(client, token)
    session_id = session["id"]

    response = client.delete(
        f"/api/agent/sessions/{session_id}",
        headers=_auth_header(token),
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0

    list_resp = client.get("/api/agent/sessions", headers=_auth_header(token))
    assert list_resp.json()["data"] == []


def test_delete_session_not_found(client: TestClient):
    token = _register_user(client)
    response = client.delete(
        "/api/agent/sessions/999999",
        headers=_auth_header(token),
    )

    assert response.status_code == 404


# ── Messages ─────────────────────────────────────────────────────────


def test_list_messages_empty(client: TestClient):
    token = _register_user(client)
    session = _create_session(client, token)
    response = client.get(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == []


def test_send_message_http(client: TestClient):
    token = _register_user(client)
    session = _create_session(client, token)
    response = client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=_auth_header(token),
        data={"content": "你好，这是一条测试消息"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["content"] == "你好，这是一条测试消息"
    assert body["data"]["role"] == "student"


def test_list_messages_after_send(client: TestClient):
    token = _register_user(client)
    session = _create_session(client, token)
    client.post(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=_auth_header(token),
        data={"content": "消息内容"},
    )
    response = client.get(
        f"/api/agent/sessions/{session['id']}/messages",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert len(body["data"]) == 1
    assert body["data"][0]["content"] == "消息内容"


# ── Upload ───────────────────────────────────────────────────────────


def test_upload_without_auth_returns_401(client: TestClient):
    response = client.post(
        "/api/agent/upload",
        files={"file": ("hw.png", b"fake-image", "image/png")},
        data={"subject": "数学"},
    )

    assert response.status_code == 401


# ── Address Suggestions ──────────────────────────────────────────────


def test_address_suggestions(client: TestClient):
    token = _register_user(client)
    response = client.get(
        "/api/agent/address-suggestions",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert isinstance(body["data"], list)


# ── Auth Guards ──────────────────────────────────────────────────────


def test_create_session_requires_auth(client: TestClient):
    response = client.post("/api/agent/sessions", params={"title": "未鉴权"})

    assert response.status_code == 401


# ── Isolation ────────────────────────────────────────────────────────


def test_session_isolation_between_users(client: TestClient):
    token_a = _register_user(client)
    _create_session(client, token_a, title="用户A的会话")

    token_b = _register_user(client)
    response = client.get("/api/agent/sessions", headers=_auth_header(token_b))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == []
