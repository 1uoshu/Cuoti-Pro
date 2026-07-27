"""Kernel integration smoke tests.

Verify the kernel starts correctly, registers tools, initializes the agent
runtime, and exercises the full register -> session -> message flow.
"""
import uuid
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ── Shared client (lifespan runs once; tool_registry is not idempotent) ────


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Registration helpers (copied from test_kernel_plugins.py) ──────────────


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


# ── 1. App starts with agent routes ───────────────────────────────────────


def test_app_starts_with_agent_routes(client):
    response = client.get("/api/plugins")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert len(body["data"]) > 0


# ── 2. Plugins have tools ─────────────────────────────────────────────────


def test_plugins_have_tools(client):
    tools = client.app.state.plugin_manager.collect_tools()

    assert len(tools) > 0


# ── 3. Tool registry populated on lifespan ─────────────────────────────────


def test_tool_registry_populated_on_lifespan(client):
    registry = client.app.state.kernel_context.capabilities.tool_registry
    tools = registry.list_all()

    assert len(tools) > 0


# ── 4. AssignmentGrading::UploadAndGrade registered ────────────────────────


def test_assignment_grading_tool_registered(client):
    registry = client.app.state.kernel_context.capabilities.tool_registry
    tool = registry.get("AssignmentGrading::UploadAndGrade")

    assert tool is not None
    assert tool.name == "AssignmentGrading::UploadAndGrade"
    assert tool.side_effect.value == "write"


# ── 5. KernelContext has all capabilities ──────────────────────────────────


def test_kernel_context_has_all_capabilities(client):
    caps = client.app.state.kernel_context.capabilities

    assert caps.agent_runtime is not None
    assert caps.tool_registry is not None
    assert caps.redis is not None
    assert caps.llm is not None
    assert caps.database is not None
    assert caps.jobs is not None
    assert caps.audit is not None
    assert caps.sandbox is not None
    assert caps.rag is not None
    assert caps.knowledge_graph is not None
    assert caps.storage is not None


# ── 6. AgentRuntime initialized ───────────────────────────────────────────


def test_agent_runtime_initialized(client):
    runtime = client.app.state.kernel_context.capabilities.agent_runtime

    assert runtime._llm is not None
    assert runtime._tool_registry is not None
    assert runtime._event_bus is not None


# ── 7. Full flow: register -> create session -> send message ───────────────


def test_full_flow_create_session_send_message(client):
    token = _register_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create session
    create_resp = client.post(
        "/api/agent/sessions",
        headers=headers,
        params={"title": "冒烟测试会话"},
    )
    assert create_resp.status_code == 200
    session_id = create_resp.json()["data"]["id"]

    # Send message
    msg_resp = client.post(
        f"/api/agent/sessions/{session_id}/messages",
        headers=headers,
        data={"content": "你好，这是一条冒烟测试消息"},
    )
    assert msg_resp.status_code == 200
    assert msg_resp.json()["data"]["role"] == "student"

    # List messages
    list_resp = client.get(
        f"/api/agent/sessions/{session_id}/messages",
        headers=headers,
    )
    assert list_resp.status_code == 200
    messages = list_resp.json()["data"]
    assert len(messages) == 1
    assert messages[0]["content"] == "你好，这是一条冒烟测试消息"


# ── 8. Full flow: tool describe ────────────────────────────────────────────


def test_full_flow_tool_describe(client):
    token = _register_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/agent/address-suggestions", headers=headers)

    assert response.status_code == 200
    tools = response.json()["data"]
    assert len(tools) > 0
    for tool in tools:
        assert "name" in tool
        assert "short_intent" in tool
        assert "side_effect" in tool


# ── 9. EventBus accessible ────────────────────────────────────────────────


def test_event_bus_accessible(client):
    runtime = client.app.state.kernel_context.capabilities.agent_runtime

    assert runtime._event_bus is not None


# ── 10. WebSocket endpoint exists ──────────────────────────────────────────


def test_websocket_endpoint_exists(client):
    from fastapi.routing import APIRouter, APIWebSocketRoute

    # Walk the full route tree, including _IncludedRouter wrappers.
    def _find_ws_paths(routes, prefix=""):
        found = []
        for route in routes:
            path = getattr(route, "path", "")
            if isinstance(route, APIWebSocketRoute):
                found.append(prefix + path)
            # _IncludedRouter exposes the original APIRouter with its prefix.
            if hasattr(route, "original_router") and isinstance(route.original_router, APIRouter):
                sub_prefix = prefix + getattr(route.original_router, "prefix", "")
                found.extend(_find_ws_paths(route.original_router.routes, sub_prefix))
            elif hasattr(route, "routes"):
                found.extend(_find_ws_paths(route.routes, prefix + path))
        return found

    ws_paths = _find_ws_paths(client.app.routes)
    assert "/api/agent/ws" in ws_paths
