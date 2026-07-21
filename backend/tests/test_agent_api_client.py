import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.kernel.agent.client import AgentAPIClient, AgentAPIError
from app.kernel.config import Settings
from app.kernel.context import build_kernel_context


def _client(handler: httpx.MockTransport) -> AgentAPIClient:
    return AgentAPIClient(
        base_url="http://agent.test",
        timeout_seconds=15,
        api_key="signed.jwt.token",
        transport=handler,
    )


def test_agent_client_grades_an_image_with_documented_multipart_contract(tmp_path: Path):
    image_path = tmp_path / "answer.png"
    image_path.write_bytes(b"png-content")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        assert request.url.path == "/api/grade/image"
        assert request.method == "POST"
        assert request.headers["authorization"] == "Bearer signed.jwt.token"
        assert b'name="student_id"' in body
        assert b"student-7" in body
        assert b'name="question"' in body
        assert "识别并批改全部题目".encode() in body
        assert b'name="subject"' in body
        assert "数学".encode() in body
        assert b'name="image"; filename="answer.png"' in body
        assert b"png-content" in body
        return httpx.Response(200, json={"data": {"questions": [{"content": "1+1"}]}})

    result = asyncio.run(
        _client(httpx.MockTransport(handler)).grade_file(
            student_id="student-7",
            file_path=image_path,
            question="识别并批改全部题目",
            subject="数学",
        )
    )

    assert result == {"questions": [{"content": "1+1"}]}


def test_agent_client_uses_pdf_field_for_pdf_upload(tmp_path: Path):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-content")

    async def handler(request: httpx.Request) -> httpx.Response:
        body = await request.aread()
        assert request.url.path == "/api/grade/pdf"
        assert b'name="pdf"; filename="paper.pdf"' in body
        assert b'name="image"' not in body
        return httpx.Response(200, json={"result": {"status": "ok"}})

    result = asyncio.run(
        _client(httpx.MockTransport(handler)).grade_file(
            student_id="3",
            file_path=pdf_path,
            question="grade all",
            subject="英语",
        )
    )

    assert result == {"status": "ok"}


def test_agent_client_sends_documented_practice_form_contract():
    async def handler(request: httpx.Request) -> httpx.Response:
        body = (await request.aread()).decode()
        assert request.url.path == "/api/practice/generate"
        assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
        assert "student_id=student-2" in body
        assert "weak_points=%E5%AF%BC%E6%95%B0" in body
        assert "difficulty=variant" in body
        return httpx.Response(200, json={"questions": [{"question": "题目"}]})

    result = asyncio.run(
        _client(httpx.MockTransport(handler)).generate_practice(
            student_id="student-2",
            weak_points="导数",
            difficulty="variant",
        )
    )

    assert result == {"questions": [{"question": "题目"}]}


def test_agent_client_serializes_question_when_grading_practice_answer():
    question = {"content": "1+1=?", "standard_answer": "2"}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = (await request.aread()).decode()
        assert request.url.path == "/api/practice/answer"
        form = httpx.QueryParams(body)
        assert form["student_id"] == "student-9"
        assert json.loads(form["question_json"]) == question
        assert form["student_answer"] == "2"
        return httpx.Response(200, json={"is_correct": True, "score": 10})

    result = asyncio.run(
        _client(httpx.MockTransport(handler)).answer_practice(
            student_id="student-9",
            question=question,
            student_answer="2",
        )
    )

    assert result["is_correct"] is True


def test_agent_client_reports_remote_validation_message():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": [{"msg": "field required"}]})

    with pytest.raises(AgentAPIError, match="422") as captured:
        asyncio.run(
            _client(httpx.MockTransport(handler)).generate_practice(
                student_id="student-2",
                weak_points="导数",
                difficulty="base",
            )
        )

    assert "field required" in str(captured.value)


def test_agent_client_redacts_jwt_echoed_by_remote_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "Authorization: Bearer signed.jwt.token"})

    with pytest.raises(AgentAPIError) as captured:
        asyncio.run(
            _client(httpx.MockTransport(handler)).generate_practice(
                student_id="student-2",
                weak_points="导数",
                difficulty="base",
            )
        )

    assert "signed.jwt.token" not in str(captured.value)
    assert "[REDACTED]" in str(captured.value)


def test_agent_client_rejects_non_object_json_response():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected"])

    with pytest.raises(AgentAPIError, match="JSON object"):
        asyncio.run(
            _client(httpx.MockTransport(handler)).generate_practice(
                student_id="student-2",
                weak_points="导数",
                difficulty="base",
            )
        )


def test_kernel_exposes_agent_client_only_when_base_url_is_configured(tmp_path: Path):
    disabled = build_kernel_context(Settings(storage_dir=str(tmp_path / "disabled")))
    enabled = build_kernel_context(
        Settings(
            storage_dir=str(tmp_path / "enabled"),
            agent_api_base_url="http://agent.internal:8010/",
            agent_api_key="signed.jwt.token",
            agent_api_timeout_seconds=90,
        )
    )

    assert disabled.capabilities.agent_api is None
    assert isinstance(enabled.capabilities.agent_api, AgentAPIClient)


def test_settings_reject_invalid_agent_api_configuration():
    with pytest.raises(RuntimeError, match="AGENT_API_BASE_URL"):
        Settings(agent_api_base_url="file:///tmp/agent").validate_startup_config()

    with pytest.raises(RuntimeError, match="AGENT_API_TIMEOUT_SECONDS"):
        Settings(
            agent_api_base_url="http://agent.internal",
            agent_api_key="signed.jwt.token",
            agent_api_timeout_seconds=0,
        ).validate_startup_config()

    with pytest.raises(RuntimeError, match="AGENT_API_KEY"):
        Settings(agent_api_base_url="http://agent.internal").validate_startup_config()
