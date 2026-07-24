import asyncio
import json
from types import SimpleNamespace

import pytest

from app.kernel.config import Settings
from app.kernel.llm import LLMAPIError, LLMGateway


class RecordingSandbox:
    def __init__(self) -> None:
        self.codes: list[str] = []

    def execute(self, code: str):
        self.codes.append(code)
        return SimpleNamespace(ok=True, value={"equivalent": True}, error=None)


class FakeHTTPResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class ScriptedHTTPClient:
    def __init__(self, payloads: list[dict], status_codes: list[int] | None = None) -> None:
        self.calls: list[dict] = []
        self.payloads = payloads
        self.status_codes = status_codes or [200] * len(payloads)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, url: str, *, json: dict):
        self.calls.append({"url": url, "json": json})
        index = len(self.calls) - 1
        return FakeHTTPResponse(self.payloads[index], self.status_codes[index])


def _final_response(text: str) -> dict:
    return {
        "id": "resp-final",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


def test_llm_gateway_runs_bounded_python_verify_tool_and_returns_final_json():
    client = ScriptedHTTPClient(
        [
            {
                "id": "resp-tool",
                "status": "completed",
                "output": [
                    {
                        "id": "reasoning-1",
                        "type": "reasoning",
                        "summary": [],
                    },
                    {
                        "call_id": "call-1",
                        "type": "function_call",
                        "name": "python_verify",
                        "arguments": json.dumps({"code": "result = {'equivalent': 1 + 1 == 2}"}),
                    }
                ],
            },
            _final_response('{"confidence": 0.99, "verified": true}'),
        ]
    )
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
            openai_reasoning_effort="xhigh",
        )
    )
    gateway._client = lambda: client
    sandbox = RecordingSandbox()

    result = asyncio.run(
        gateway.chat_json_with_python(
            "system",
            "verify this",
            sandbox,
            temperature=0.1,
            max_tokens=500,
            max_tool_calls=2,
        )
    )

    assert result == {"confidence": 0.99, "verified": True}
    assert sandbox.codes == ["result = {'equivalent': 1 + 1 == 2}"]
    assert client.calls[0]["url"] == "https://example.com/responses"
    first_request = client.calls[0]["json"]
    assert first_request["tools"][0]["name"] == "python_verify"
    assert first_request["tool_choice"] == {"type": "function", "name": "python_verify"}
    assert first_request["reasoning"] == {"effort": "xhigh"}
    assert first_request["store"] is False
    assert "temperature" not in first_request
    assert client.calls[1]["json"]["tool_choice"] == "auto"
    replayed_output = client.calls[1]["json"]["input"][1:-1]
    assert replayed_output == client.payloads[0]["output"]
    tool_output = client.calls[1]["json"]["input"][-1]
    assert tool_output["type"] == "function_call_output"
    assert json.loads(tool_output["output"]) == {
        "ok": True,
        "value": {"equivalent": True},
        "error": None,
    }


def test_llm_gateway_rejects_a_tool_call_without_call_id_before_execution():
    client = ScriptedHTTPClient(
        [
            {
                "id": "resp-tool",
                "status": "completed",
                "output": [
                    {
                        "type": "function_call",
                        "name": "python_verify",
                        "arguments": json.dumps({"code": "result = {'executed': True}"}),
                    }
                ],
            }
        ]
    )
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
        )
    )
    gateway._client = lambda: client
    sandbox = RecordingSandbox()

    with pytest.raises(LLMAPIError, match="without call_id"):
        asyncio.run(
            gateway.chat_json_with_python(
                "system",
                "verify this",
                sandbox,
                temperature=0.1,
                max_tokens=500,
            )
        )

    assert sandbox.codes == []


def test_llm_gateway_returns_invalid_tool_arguments_without_execution():
    client = ScriptedHTTPClient(
        [
            {
                "id": "resp-tool",
                "status": "completed",
                "output": [
                    {
                        "call_id": "call-1",
                        "type": "function_call",
                        "name": "python_verify",
                        "arguments": json.dumps(
                            {
                                "code": "result = {'executed': True}",
                                "unexpected": "field",
                            }
                        ),
                    }
                ],
            },
            _final_response('{"confidence": 0.99, "verified": true}'),
        ]
    )
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
        )
    )
    gateway._client = lambda: client
    sandbox = RecordingSandbox()

    with pytest.raises(LLMAPIError, match="without successful python verification"):
        asyncio.run(
            gateway.chat_json_with_python(
                "system",
                "verify this",
                sandbox,
                temperature=0.1,
                max_tokens=500,
            )
        )

    assert sandbox.codes == []
    assert client.calls[1]["json"]["tool_choice"] == {"type": "function", "name": "python_verify"}
    tool_output = json.loads(client.calls[1]["json"]["input"][-1]["output"])
    assert tool_output["ok"] is False
    assert "exactly one code field" in tool_output["error"]


def test_llm_gateway_sends_multimodal_input_through_responses_api():
    client = ScriptedHTTPClient([_final_response('{"confidence": 0.99, "verified": true}')])
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
            openai_reasoning_effort="high",
        )
    )
    gateway._client = lambda: client

    result = asyncio.run(
        gateway.vision_json_many(
            "grade every page",
            "assignment",
            ["data:image/png;base64,AAAA", "data:image/png;base64,BBBB"],
            temperature=0.1,
            max_tokens=800,
        )
    )

    assert result == {"confidence": 0.99, "verified": True}
    request = client.calls[0]["json"]
    assert request["instructions"] == "grade every page"
    content = request["input"][0]["content"]
    assert [item["type"] for item in content] == [
        "input_text",
        "input_image",
        "input_image",
    ]
    assert [item["image_url"] for item in content[1:]] == [
        "data:image/png;base64,AAAA",
        "data:image/png;base64,BBBB",
    ]
    assert all(item["detail"] == "auto" for item in content[1:])


def test_llm_gateway_omits_reasoning_for_non_reasoning_models():
    client = ScriptedHTTPClient([_final_response('{"answer": "ok"}')])
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="non-reasoning-model",
            openai_reasoning_effort="none",
        )
    )
    gateway._client = lambda: client

    result = asyncio.run(
        gateway.chat_json(
            "system",
            "request",
            temperature=0.25,
            max_tokens=100,
        )
    )

    assert result == {"answer": "ok"}
    request = client.calls[0]["json"]
    assert "reasoning" not in request
    assert request["temperature"] == 0.25


def test_llm_gateway_redacts_credentials_echoed_by_provider_errors():
    client = ScriptedHTTPClient(
        [{"error": {"message": "request blocked for secret-test-key"}}],
        status_codes=[403],
    )
    gateway = LLMGateway(
        Settings(
            openai_api_key="secret-test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
        )
    )
    gateway._client = lambda: client

    with pytest.raises(LLMAPIError, match="HTTP 403: request blocked") as raised:
        asyncio.run(
            gateway.chat_json(
                "system",
                "request",
                temperature=0,
                max_tokens=100,
            )
        )

    assert "secret-test-key" not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)


def test_llm_gateway_rejects_incomplete_responses_even_with_parseable_output():
    client = ScriptedHTTPClient(
        [
            {
                "id": "resp-incomplete",
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": '{"confidence": 0.1}'}],
                    }
                ],
            }
        ]
    )
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
        )
    )
    gateway._client = lambda: client

    with pytest.raises(LLMAPIError, match="incomplete.*max_output_tokens"):
        asyncio.run(
            gateway.chat_json(
                "system",
                "request",
                temperature=0,
                max_tokens=100,
            )
        )


def test_llm_gateway_rejects_a_response_without_status():
    client = ScriptedHTTPClient([{"output_text": '{"confidence": 0.99}'}])
    gateway = LLMGateway(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://example.com",
            openai_model="test-model",
        )
    )
    gateway._client = lambda: client

    with pytest.raises(LLMAPIError, match="missing or invalid status"):
        asyncio.run(
            gateway.chat_json(
                "system",
                "request",
                temperature=0,
                max_tokens=100,
            )
        )
