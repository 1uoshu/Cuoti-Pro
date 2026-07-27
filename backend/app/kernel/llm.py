import asyncio
import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.kernel.config import Settings


class LLMAPIError(RuntimeError):
    """A bounded, credential-safe model provider error."""


@dataclass
class StreamEvent:
    """SSE event yielded by LLMGateway.stream_chat()."""

    type: str  # "text_delta" | "tool_call" | "done" | "error"
    delta: str = ""
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_call_id: str = ""
    error: str = ""


class LLMGateway:
    """Kernel-owned raw HTTP client for the OpenAI Responses wire protocol."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _client(self) -> httpx.AsyncClient:
        self._settings.validate_model_config()
        return httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._settings.openai_timeout_seconds,
        )

    @property
    def model(self) -> str:
        return self._settings.openai_model

    @property
    def fast_model(self) -> str:
        """轻量模型（意图分流/决策用），未配置时回退到主模型"""
        return self._settings.effective_fast_model

    @property
    def chat_completions_url(self) -> str:
        base_url = self._settings.openai_base_url or "https://api.openai.com/v1"
        return f"{base_url.rstrip('/')}/chat/completions"

    @property
    def responses_url(self) -> str:
        """保留向后兼容（旧方法如 chat_json 仍用 Responses API）"""
        base_url = self._settings.openai_base_url or "https://api.openai.com/v1"
        return f"{base_url.rstrip('/')}/responses"

    @staticmethod
    def extract_json(raw_response: str) -> dict[str, Any]:
        text = raw_response.strip()
        if "```" in text:
            sections = text.split("```")
            if len(sections) >= 3:
                text = sections[1].removeprefix("json").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("模型没有返回 JSON 对象")
        return json.loads(text[start : end + 1])

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        request = {
            "instructions": system_prompt,
            "input": user_prompt,
            **self._response_options(temperature=temperature, max_tokens=max_tokens),
        }
        async with self._client() as client:
            response = await self._post_response(client, request)
        return self.extract_json(self._output_text(response))

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        model: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream a chat response via Chat Completions API with function calling.

        DeepSeek and most providers use /chat/completions, not /responses.
        SSE format: data: {"choices":[{"delta":{...}}]}

        Args:
            messages: Chat Completions format message list (role: system/user/assistant/tool).
            tools: Responses-API-style tool defs; auto-converted to Chat Completions format.
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            model: Override model (default: self.model).

        Yields:
            StreamEvent instances: text_delta, tool_call, done, or error.
        """
        # Convert tool schemas to Chat Completions format
        # Note: DeepSeek only allows [a-zA-Z0-9_-] in function names, so :: -> __
        cc_tools = None
        _name_map: dict[str, str] = {}  # api_name -> original_name
        if tools:
            cc_tools = []
            for t in tools:
                api_name = t["name"].replace("::", "__")
                _name_map[api_name] = t["name"]
                cc_tools.append({
                    "type": "function",
                    "function": {
                        "name": api_name,
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                })

        request: dict[str, Any] = {
            "messages": messages,
            "model": model or self.model,
            "max_tokens": max_tokens,
            "stream": True,
            "temperature": temperature,
        }
        if cc_tools:
            request["tools"] = cc_tools
            request["parallel_tool_calls"] = False

        # Accumulate streaming tool_call deltas (Chat Completions sends args incrementally)
        _pending: dict[int, dict] = {}

        try:
            async with self._client() as client:
                async with client.stream("POST", self.chat_completions_url, json=request) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        try:
                            payload = json.loads(body)
                        except ValueError:
                            payload = None
                        message = self._error_message(payload)
                        yield StreamEvent(type="error", error=f"HTTP {response.status_code}: {message}")
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if raw == "[DONE]":
                            for tc in _pending.values():
                                if tc.get("name"):
                                    try:
                                        args = json.loads(tc.get("arguments", "{}"))
                                    except json.JSONDecodeError:
                                        args = {}
                                    original_name = _name_map.get(tc["name"], tc["name"])
                                    yield StreamEvent(type="tool_call", tool_name=original_name,
                                                     tool_args=args if isinstance(args, dict) else {},
                                                     tool_call_id=tc.get("id", ""))
                            _pending.clear()
                            yield StreamEvent(type="done")
                            return
                        if not raw:
                            continue
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})

                        # Text content (skip reasoning_content from DeepSeek)
                        content = delta.get("content")
                        if content:
                            yield StreamEvent(type="text_delta", delta=content)

                        # Tool call deltas (incremental)
                        for tc_delta in delta.get("tool_calls", []):
                            idx = tc_delta.get("index", 0)
                            if idx not in _pending:
                                _pending[idx] = {"id": "", "name": "", "arguments": ""}
                            tc = _pending[idx]
                            if tc_delta.get("id"):
                                tc["id"] = tc_delta["id"]
                            func = tc_delta.get("function", {})
                            if func.get("name"):
                                tc["name"] = func["name"]
                            if func.get("arguments"):
                                tc["arguments"] += func["arguments"]

                        # Finish reason
                        finish = choices[0].get("finish_reason")
                        if finish in ("stop", "tool_calls", "length"):
                            for tc in _pending.values():
                                if tc.get("name"):
                                    try:
                                        args = json.loads(tc.get("arguments", "{}"))
                                    except json.JSONDecodeError:
                                        args = {}
                                    original_name = _name_map.get(tc["name"], tc["name"])
                                    yield StreamEvent(type="tool_call", tool_name=original_name,
                                                     tool_args=args if isinstance(args, dict) else {},
                                                     tool_call_id=tc.get("id", ""))
                            _pending.clear()
                            yield StreamEvent(type="done")
                            return

        except httpx.TimeoutException:
            yield StreamEvent(type="error", error="连接超时")
        except httpx.HTTPError as exc:
            yield StreamEvent(type="error", error=f"传输失败: {type(exc).__name__}")

    async def chat_json_with_python(
        self,
        system_prompt: str,
        user_prompt: str,
        sandbox: Any,
        *,
        temperature: float,
        max_tokens: int,
        max_tool_calls: int = 3,
    ) -> dict[str, Any]:
        return await self._json_with_python(
            system_prompt,
            [{"role": "user", "content": [{"type": "input_text", "text": user_prompt}]}],
            sandbox,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_calls=max_tool_calls,
        )

    async def vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_url: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        return await self.vision_json_many(
            system_prompt,
            user_prompt,
            [image_data_url],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def vision_json_many(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        if not image_data_urls:
            raise ValueError("多模态请求至少需要一张图片")
        request = {
            "instructions": system_prompt,
            "input": [self._vision_input(user_prompt, image_data_urls)],
            **self._response_options(temperature=temperature, max_tokens=max_tokens),
        }
        async with self._client() as client:
            response = await self._post_response(client, request)
        return self.extract_json(self._output_text(response))

    async def vision_json_many_with_python(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        sandbox: Any,
        *,
        temperature: float,
        max_tokens: int,
        max_tool_calls: int = 3,
    ) -> dict[str, Any]:
        if not image_data_urls:
            raise ValueError("多模态请求至少需要一张图片")
        return await self._json_with_python(
            system_prompt,
            [self._vision_input(user_prompt, image_data_urls)],
            sandbox,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_calls=max_tool_calls,
        )

    async def _json_with_python(
        self,
        instructions: str,
        input_items: list[Any],
        sandbox: Any,
        *,
        temperature: float,
        max_tokens: int,
        max_tool_calls: int,
    ) -> dict[str, Any]:
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        tools = [
            {
                "type": "function",
                "name": "python_verify",
                "description": (
                    "Run a deterministic math or physics verification in a restricted Python sandbox. "
                    "Allowed libraries: math, statistics, fractions, decimal, sympy, and pint. "
                    "Assign a JSON-serializable verification result to the variable result."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Restricted Python code that assigns its output to result.",
                        }
                    },
                    "required": ["code"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        ]
        attempted_tool_calls = 0
        successful_tool_calls = 0

        async with self._client() as client:
            while True:
                tool_choice: Any = (
                    {"type": "function", "name": "python_verify"}
                    if successful_tool_calls == 0
                    else "auto"
                )
                request = {
                    "instructions": instructions,
                    "input": input_items,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "parallel_tool_calls": False,
                    **self._response_options(temperature=temperature, max_tokens=max_tokens),
                }
                response = await self._post_response(client, request)
                output = response.get("output")
                if not isinstance(output, list):
                    raise LLMAPIError("Responses API result is missing an output list")
                tool_calls = [item for item in output if isinstance(item, dict) and item.get("type") == "function_call"]
                if not tool_calls:
                    if successful_tool_calls == 0:
                        raise LLMAPIError("model returned a result without successful python verification")
                    return self.extract_json(self._output_text(response))
                if attempted_tool_calls + len(tool_calls) > max_tool_calls:
                    raise LLMAPIError("model exceeded the python_verify tool-call limit")

                input_items.extend(output)
                for call in tool_calls:
                    attempted_tool_calls += 1
                    call_id = call.get("call_id")
                    if not isinstance(call_id, str) or not call_id:
                        raise LLMAPIError("model returned a python tool call without call_id")
                    result = await self._run_python_tool(
                        call.get("name"),
                        call.get("arguments"),
                        sandbox,
                    )
                    if result.get("ok") is True:
                        successful_tool_calls += 1
                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result, ensure_ascii=False),
                        }
                    )

    async def _post_response(self, client: httpx.AsyncClient, request: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await client.post(self.responses_url, json=request)
        except httpx.HTTPError as exc:
            raise LLMAPIError(f"Responses API transport failed: {type(exc).__name__}") from None

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            message = self._error_message(payload)
            raise LLMAPIError(f"Responses API returned HTTP {response.status_code}: {message}")
        if not isinstance(payload, dict):
            raise LLMAPIError("Responses API returned a non-object JSON body")
        if payload.get("error"):
            raise LLMAPIError(f"Responses API failed: {self._error_message(payload.get('error'))}")
        response_status = payload.get("status")
        if not isinstance(response_status, str):
            raise LLMAPIError("Responses API result is missing or invalid status")
        if response_status != "completed":
            details = payload.get("incomplete_details") or response_status
            raise LLMAPIError(
                f"Responses API returned status {response_status}: {self._error_message(details)}"
            )
        return payload

    def _response_options(self, *, temperature: float, max_tokens: int) -> dict[str, Any]:
        options: dict[str, Any] = {
            "model": self.model,
            "max_output_tokens": max_tokens,
            "store": not self._settings.openai_disable_response_storage,
        }
        if self._settings.openai_reasoning_effort == "none":
            options["temperature"] = temperature
        else:
            options["reasoning"] = {"effort": self._settings.openai_reasoning_effort}
        return options

    @staticmethod
    def _vision_input(user_prompt: str, image_data_urls: list[str]) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {"type": "input_text", "text": user_prompt},
                *[
                    {"type": "input_image", "image_url": image_data_url, "detail": "auto"}
                    for image_data_url in image_data_urls
                ],
            ],
        }

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        direct_text = response.get("output_text")
        if isinstance(direct_text, str) and direct_text:
            return direct_text

        texts: list[str] = []
        output = response.get("output")
        if isinstance(output, list):
            for item in output:
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                content = item.get("content")
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text" and isinstance(part.get("text"), str):
                        texts.append(part["text"])
        if not texts:
            raise LLMAPIError("Responses API result does not contain output text")
        return "\n".join(texts)

    def _error_message(self, payload: Any) -> str:
        message = "provider rejected the request"
        if isinstance(payload, dict):
            error = payload.get("error", payload)
            if isinstance(error, dict):
                for field in ("message", "detail", "reason", "code"):
                    candidate = error.get(field)
                    if isinstance(candidate, str) and candidate:
                        message = candidate
                        break
            elif isinstance(error, str) and error:
                message = error
        elif isinstance(payload, str) and payload:
            message = payload
        api_key = self._settings.openai_api_key
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        return message[:500]

    @staticmethod
    async def _run_python_tool(name: Any, arguments: Any, sandbox: Any) -> dict[str, Any]:
        if not isinstance(name, str) or name != "python_verify":
            return {"ok": False, "value": None, "error": f"unknown tool: {name}"}
        if not isinstance(arguments, str):
            return {"ok": False, "value": None, "error": "invalid tool arguments: expected a JSON string"}
        try:
            payload = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return {"ok": False, "value": None, "error": f"invalid tool arguments: {exc}"}
        if not isinstance(payload, dict) or set(payload) != {"code"}:
            return {
                "ok": False,
                "value": None,
                "error": "invalid tool arguments: expected exactly one code field",
            }
        code = payload["code"]
        if not isinstance(code, str):
            return {"ok": False, "value": None, "error": "invalid tool arguments: code must be a string"}

        execution = await asyncio.to_thread(sandbox.execute, code)
        return {"ok": execution.ok, "value": execution.value, "error": execution.error}
