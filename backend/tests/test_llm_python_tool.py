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


def _chat_completion(text: str) -> dict:
    """Chat Completions 最终答复（无 tool_calls）。"""
    return {
        "id": "chatcmpl-final",
        "choices": [{"message": {"role": "assistant", "content": text}}],
    }


def _tool_call_response(call_id: str, code: str, *, extra_args: dict | None = None) -> dict:
    """Chat Completions 里带 python_verify 工具调用的一轮答复。"""
    arguments = {"code": code}
    if extra_args:
        arguments.update(extra_args)
    return {
        "id": "chatcmpl-tool",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "python_verify",
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ],
    }


def _gateway(client, **overrides) -> LLMGateway:
    params = {
        "openai_api_key": "test-key",
        "openai_base_url": "https://example.com/v1",
        "openai_model": "test-model",
    }
    params.update(overrides)
    settings = Settings(**params)
    gateway = LLMGateway(settings)
    gateway._client = lambda: client
    gateway._vision_client = lambda: client
    return gateway


def test_llm_gateway_runs_bounded_python_verify_tool_and_returns_final_json():
    client = ScriptedHTTPClient(
        [
            _tool_call_response("call-1", "result = {'equivalent': 1 + 1 == 2}"),
            _chat_completion('{"confidence": 0.99, "verified": true}'),
        ]
    )
    gateway = _gateway(client, openai_reasoning_effort="xhigh")
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

    # 两轮都打到 Chat Completions 端点
    assert client.calls[0]["url"] == "https://example.com/v1/chat/completions"
    first_request = client.calls[0]["json"]
    assert first_request["tools"][0]["function"]["name"] == "python_verify"
    # 首轮强制验算
    assert first_request["tool_choice"] == {"type": "function", "function": {"name": "python_verify"}}
    assert first_request["thinking"] == {"type": "disabled"}
    # 之后交给模型自主决定
    assert client.calls[1]["json"]["tool_choice"] == "auto"

    # 第二轮消息序列：system + user + 带 tool_calls 的 assistant + tool 结果
    replayed = client.calls[1]["json"]["messages"]
    assert replayed[0]["role"] == "system"
    assert replayed[1]["role"] == "user"
    assert replayed[-2]["role"] == "assistant"
    assert replayed[-2]["tool_calls"][0]["id"] == "call-1"
    tool_message = replayed[-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"]) == {
        "ok": True,
        "value": {"equivalent": True},
        "error": None,
    }


def test_llm_gateway_rejects_a_tool_call_without_id_before_execution():
    client = ScriptedHTTPClient([_tool_call_response("", "result = {'executed': True}")])
    gateway = _gateway(client)
    sandbox = RecordingSandbox()

    with pytest.raises(LLMAPIError, match="without id"):
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


def test_llm_gateway_feeds_invalid_tool_arguments_back_without_executing_sandbox():
    # 参数非法（多了一个字段）不再直接崩溃：把错误回喂给模型，让它据此产出最终 JSON。
    client = ScriptedHTTPClient(
        [
            _tool_call_response("call-1", "result = {'executed': True}", extra_args={"unexpected": "field"}),
            _chat_completion('{"confidence": 0.99, "verified": true}'),
        ]
    )
    gateway = _gateway(client)
    sandbox = RecordingSandbox()

    result = asyncio.run(
        gateway.chat_json_with_python(
            "system",
            "verify this",
            sandbox,
            temperature=0.1,
            max_tokens=500,
        )
    )

    assert result == {"confidence": 0.99, "verified": True}
    # 非法参数不进沙箱
    assert sandbox.codes == []
    tool_output = json.loads(client.calls[1]["json"]["messages"][-1]["content"])
    assert tool_output["ok"] is False
    assert "exactly one code field" in tool_output["error"]


def test_llm_gateway_sends_multimodal_input_through_chat_completions():
    client = ScriptedHTTPClient([_chat_completion('{"confidence": 0.99, "verified": true}')])
    gateway = _gateway(client, vision_base_url="https://vision.example.com/v1")

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
    assert client.calls[0]["url"] == "https://vision.example.com/v1/chat/completions"
    assert request["messages"][0] == {"role": "system", "content": "grade every page"}
    content = request["messages"][1]["content"]
    assert [item["type"] for item in content] == ["text", "image_url", "image_url"]
    assert [item["image_url"]["url"] for item in content[1:]] == [
        "data:image/png;base64,AAAA",
        "data:image/png;base64,BBBB",
    ]


def test_llm_gateway_chat_json_sends_temperature_and_omits_responses_only_fields():
    client = ScriptedHTTPClient([_chat_completion('{"answer": "ok"}')])
    gateway = _gateway(client, openai_model="non-reasoning-model", openai_reasoning_effort="none")

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
    # Chat Completions 请求：无 Responses-API 专有字段
    assert "reasoning" not in request
    assert "store" not in request
    assert request["temperature"] == 0.25
    assert request["messages"][0]["role"] == "system"


def test_llm_gateway_redacts_credentials_echoed_by_provider_errors():
    client = ScriptedHTTPClient(
        [{"error": {"message": "request blocked for secret-test-key"}}],
        status_codes=[403],
    )
    gateway = _gateway(client, openai_api_key="secret-test-key")

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


def test_llm_gateway_rejects_a_response_with_no_choices():
    # Chat Completions 没有 choices（也没有 output_text 兜底）→ 明确报错，不静默返回空。
    client = ScriptedHTTPClient([{"id": "chatcmpl-empty", "choices": []}])
    gateway = _gateway(client)

    with pytest.raises(LLMAPIError, match="does not contain output text"):
        asyncio.run(
            gateway.chat_json(
                "system",
                "request",
                temperature=0,
                max_tokens=100,
            )
        )


def test_llm_gateway_python_loop_raises_when_provider_returns_no_choices():
    client = ScriptedHTTPClient([{"id": "chatcmpl-empty", "choices": []}])
    gateway = _gateway(client)
    sandbox = RecordingSandbox()

    with pytest.raises(LLMAPIError, match="no choices"):
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
