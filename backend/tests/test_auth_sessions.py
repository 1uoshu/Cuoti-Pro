from __future__ import annotations

from hashlib import sha256
import uuid

from fastapi.testclient import TestClient

from app.kernel.auth.security import decode_access_token
from app.kernel.auth.sessions import revoke_token
from app.kernel.context import get_kernel_context
from app.main import app


def test_first_registered_user_is_admin_and_later_users_are_students():
    with TestClient(app) as client:
        admin_token = register(client, f"admin_{uuid.uuid4().hex[:12]}")
        student_token = register(client, f"student_{uuid.uuid4().hex[:12]}")

        assert client.get("/api/auth/me", headers=auth_header(admin_token)).json()["data"]["role"] == "admin"
        assert client.get("/api/auth/me", headers=auth_header(student_token)).json()["data"]["role"] == "student"


def test_pow_challenge_rejects_replay_purpose_and_context_mismatch():
    with TestClient(app) as client:
        challenge = get_challenge(client, "register")
        payload = registration_payload("replay") | pow_payload(challenge)
        assert client.post("/api/auth/register", json=payload).status_code == 200
        replay = client.post("/api/auth/register", json=registration_payload("replay_again") | pow_payload(challenge))
        assert replay.status_code == 429

        login_challenge = get_challenge(client, "login")
        purpose_mismatch = client.post(
            "/api/auth/register", json=registration_payload("mismatch") | pow_payload(login_challenge)
        )
        assert purpose_mismatch.status_code == 400

        context_challenge = get_challenge(client, "register", headers={"User-Agent": "challenge-agent"})
        context_mismatch = client.post(
            "/api/auth/register",
            headers={"User-Agent": "other-agent"},
            json=registration_payload("context") | pow_payload(context_challenge),
        )
        assert context_mismatch.status_code == 400


def test_redis_whitelist_logout_and_password_change_revoke_tokens():
    with TestClient(app) as client:
        username = f"session_{uuid.uuid4().hex[:12]}"
        first_token = register(client, username)
        second_token = login(client, username)

        revoke_token(get_kernel_context().capabilities.redis, decode_access_token(first_token))
        assert client.get("/api/auth/me", headers=auth_header(first_token)).status_code == 401
        assert client.get("/api/auth/me", headers=auth_header(second_token)).status_code == 200

        password_update = client.put(
            "/api/auth/password",
            headers=auth_header(second_token),
            json={"current_password": "password123", "new_password": "newpassword123"},
        )
        assert password_update.status_code == 200
        assert client.get("/api/auth/me", headers=auth_header(second_token)).status_code == 401

        fresh_token = login(client, username, password="newpassword123")
        logout = client.post("/api/auth/logout", headers=auth_header(fresh_token))
        assert logout.status_code == 200
        assert client.get("/api/auth/me", headers=auth_header(fresh_token)).status_code == 401


def test_near_expiry_session_returns_replacement_token():
    settings = get_kernel_context().settings
    original_threshold = settings.token_refresh_threshold_minutes
    settings.token_refresh_threshold_minutes = settings.jwt_expire_hours * 60
    try:
        with TestClient(app) as client:
            token = register(client, f"renew_{uuid.uuid4().hex[:12]}")
            response = client.get("/api/auth/me", headers=auth_header(token))
    finally:
        settings.token_refresh_threshold_minutes = original_threshold

    assert response.status_code == 200
    renewed_token = response.headers.get("Set-Token")
    assert renewed_token and renewed_token != token
    assert client.get("/api/auth/me", headers=auth_header(renewed_token)).status_code == 200


def test_only_admin_can_manage_users_config_and_audit_exports():
    with TestClient(app) as client:
        admin_token = login(client, _first_admin_username())
        student_token = register(client, f"managed_{uuid.uuid4().hex[:12]}")

        assert client.get("/api/admin/users", headers=auth_header(student_token)).status_code == 403
        users = client.get("/api/admin/users", headers=auth_header(admin_token))
        assert users.status_code == 200
        assert any(item["role"] == "admin" for item in users.json()["data"]["items"])

        config = client.put(
            "/api/admin/config",
            headers=auth_header(admin_token),
            json={"openai_api_key": "sk-test-secret", "openai_model": "gpt-test", "pow_difficulty": 3},
        )
        assert config.status_code == 200
        assert config.json()["data"]["openai_api_key_configured"] is True
        assert "openai_api_key" not in config.json()["data"]

        assert client.get("/api/audit-logs", headers=auth_header(student_token)).status_code == 403
        audit = client.get("/api/audit-logs", headers=auth_header(admin_token))
        assert audit.status_code == 200
        exported = client.get("/api/audit-logs/export", headers=auth_header(admin_token))
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith("text/csv")
        assert "event_type" in exported.text


def _first_admin_username() -> str:
    from app.kernel.database import SessionLocal
    from app.kernel.models import User
    from sqlalchemy import select

    with SessionLocal() as db:
        return db.scalar(select(User.username).where(User.role == "admin"))


def get_challenge(client: TestClient, purpose: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
    response = client.get("/api/auth/pow/challenge", params={"purpose": purpose}, headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def register(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/auth/register", json=registration_payload(username) | pow_payload(get_challenge(client, "register"))
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def login(client: TestClient, username: str, *, password: str = "password123") -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password} | pow_payload(get_challenge(client, "login")),
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def registration_payload(username: str) -> dict[str, str]:
    return {"username": username, "password": "password123", "nickname": "会话测试"}


def pow_payload(challenge: dict[str, object]) -> dict[str, str]:
    return {"pow_challenge_id": str(challenge["challenge_id"]), "pow_nonce": solve_pow(challenge)}


def solve_pow(challenge: dict[str, object]) -> str:
    prefix = "0" * int(challenge["difficulty"])
    nonce_seed = str(challenge["nonce_seed"])
    nonce = 0
    while True:
        candidate = str(nonce)
        if sha256(f"{nonce_seed}:{candidate}".encode()).hexdigest().startswith(prefix):
            return candidate
        nonce += 1


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
