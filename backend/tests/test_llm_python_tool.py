import asyncio
import json
from types import SimpleNamespace

from app.kernel.config import Settings
from app.kernel.llm import LLMGateway


class RecordingSandbox:
    def __init__(self) -> None:
        self.codes: list[str] = []

    def execute(self, code: str):
        self.codes.append(code)
        return SimpleNamespace(ok=True, value={"equivalent": True}, error=None)


class ScriptedCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            message = SimpleNamespace(
                content=None,
                tool_calls=[
                    SimpleNamespace(
                        id="call-1",
                        type="function",
                        function=SimpleNamespace(
                            name="python_verify",
                            arguments=json.dumps({"code": "result = {'equivalent': 1 + 1 == 2}"}),
                        ),
                    )
                ],
            )
        else:
            message = SimpleNamespace(content='{"confidence": 0.99, "verified": true}', tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_llm_gateway_runs_bounded_python_verify_tool_and_returns_final_json():
    completions = ScriptedCompletions()
    gateway = LLMGateway(Settings(openai_api_key="test-key", openai_model="test-model"))
    gateway._client = lambda: SimpleNamespace(chat=SimpleNamespace(completions=completions))
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
    assert completions.calls[0]["tools"][0]["function"]["name"] == "python_verify"
    tool_message = completions.calls[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"]) == {
        "ok": True,
        "value": {"equivalent": True},
        "error": None,
    }

