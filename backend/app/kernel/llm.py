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
            timeout=None,  # 不限制超时，工具调用可能耗时很长
        )

    def _vision_client(self) -> httpx.AsyncClient:
        """视觉模型专用 HTTP 客户端（SiliconFlow/Qwen3-VL）"""
        api_key = self._settings.vision_api_key or self._settings.openai_api_key
        return httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=None,  # 不限制超时，视觉模型可能很慢
        )

    @property
    def model(self) -> str:
        return self._settings.openai_model

    @property
    def fast_model(self) -> str:
        """轻量模型（意图分流/决策用），未配置时回退到主模型"""
        return self._settings.effective_fast_model

    @property
    def vision_model(self) -> str:
        """视觉模型（多模态任务用）"""
        return self._settings.vision_model

    @property
    def vision_chat_completions_url(self) -> str:
        base_url = self._settings.vision_base_url or "https://api.siliconflow.cn/v1"
        return f"{base_url.rstrip('/')}/chat/completions"

    @property
    def chat_completions_url(self) -> str:
        base_url = self._settings.openai_base_url or "https://api.openai.com/v1"
        return f"{base_url.rstrip('/')}/chat/completions"

    @property
    def responses_url(self) -> str:
        """保留向后兼容（旧方法如 chat_json 仍用 Responses API）"""
        base_url = self._settings.openai_base_url or "https://api.openai.com/v1"
        return f"{base_url.rstrip('/')}/responses"

    @property
    def chat_completions_url(self) -> str:
        base_url = self._settings.openai_base_url or "https://api.openai.com/v1"
        return f"{base_url.rstrip('/')}/chat/completions"

    async def chat_completions_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """Chat Completions API — compatible with DeepSeek, Qwen, and other non-OpenAI providers."""
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with self._client() as client:
            try:
                response = await client.post(self.chat_completions_url, json=request)
            except httpx.HTTPError as exc:
                raise LLMAPIError(f"Chat Completions transport failed: {type(exc).__name__}") from None
            if response.status_code >= 400:
                raise LLMAPIError(f"Chat Completions returned HTTP {response.status_code}: {response.text[:500]}")
            payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise LLMAPIError("Chat Completions returned empty content")
        return self.extract_json(content)

    async def chat_completions_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Chat Completions API — returns raw text (no JSON parsing)."""
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with self._client() as client:
            try:
                response = await client.post(self.chat_completions_url, json=request)
            except httpx.HTTPError as exc:
                raise LLMAPIError(f"Chat Completions transport failed: {type(exc).__name__}") from None
            if response.status_code >= 400:
                raise LLMAPIError(f"Chat Completions returned HTTP {response.status_code}: {response.text[:500]}")
            payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise LLMAPIError("Chat Completions returned empty content")
        return content

    async def vision_chat_completions(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_url: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Vision Chat Completions — uses VISION_* env vars for multimodal models."""
        vision_key = self._settings.vision_api_key or self._settings.openai_api_key
        vision_base = self._settings.vision_base_url or self._settings.openai_base_url or "https://api.openai.com/v1"
        vision_model = self._settings.vision_model or self._settings.openai_model
        vision_url = f"{vision_base.rstrip('/')}/chat/completions"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]},
        ]
        request = {
            "model": vision_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {vision_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(headers=headers, timeout=60) as client:
            try:
                response = await client.post(vision_url, json=request)
            except httpx.HTTPError as exc:
                raise LLMAPIError(f"Vision API transport failed: {type(exc).__name__}") from None
            if response.status_code >= 400:
                raise LLMAPIError(f"Vision API returned HTTP {response.status_code}: {response.text[:500]}")
            payload = response.json()
        content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            raise LLMAPIError("Vision API returned empty content")
        return content

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
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
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
        # Build multimodal content for Chat Completions API
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for url in image_data_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        request = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "model": self.vision_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with self._vision_client() as client:
            response = await self._post_vision(client, request)
        return self.extract_json(self._output_text(response))

    async def vision_ocr(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_urls: list[str],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """纯视觉识别/OCR，不走 function calling。

        用于：图片 → 文本内容提取。
        返回模型的原始文本回复。
        """
        if not image_data_urls:
            raise ValueError("多模态请求至少需要一张图片")
        content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
        for url in image_data_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        request = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "model": self.vision_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with self._vision_client() as client:
            response = await self._post_vision(client, request)
        return self._output_text(response)

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
            model=self.vision_model,
            use_vision_client=True,
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
        model: str | None = None,
        use_vision_client: bool = False,
    ) -> dict[str, Any]:
        """Chat Completions API with python_verify function calling."""
        target_model = model or self.model
        if max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")
        tools = [
            {
                "type": "function",
                "function": {
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
                    },
                },
            }
        ]

        # Build initial messages: system + user content
        messages: list[dict[str, Any]] = [{"role": "system", "content": instructions}]
        # Convert input_items to messages format
        for item in input_items:
            if isinstance(item, dict):
                if item.get("role") == "user":
                    # Convert Responses API content format to Chat Completions
                    content = item.get("content", "")
                    if isinstance(content, list):
                        # Multimodal content
                        cc_content = []
                        for part in content:
                            if isinstance(part, dict):
                                if part.get("type") == "input_text":
                                    cc_content.append({"type": "text", "text": part.get("text", "")})
                                elif part.get("type") == "input_image":
                                    cc_content.append({
                                        "type": "image_url",
                                        "image_url": {"url": part.get("image_url", ""), "detail": part.get("detail", "auto")},
                                    })
                        messages.append({"role": "user", "content": cc_content})
                    else:
                        messages.append({"role": "user", "content": content})
                elif item.get("role") == "assistant":
                    messages.append({"role": "assistant", "content": item.get("content", "")})
                elif item.get("type") == "function_call_output":
                    messages.append({
                        "role": "tool",
                        "tool_call_id": item.get("call_id", ""),
                        "content": item.get("output", ""),
                    })
            elif isinstance(item, str):
                messages.append({"role": "user", "content": item})

        attempted_tool_calls = 0
        successful_tool_calls = 0

        client_ctx = self._vision_client() if use_vision_client else self._client()
        async with client_ctx as client:
            while True:
                tool_choice: Any = (
                    {"type": "function", "function": {"name": "python_verify"}}
                    if successful_tool_calls == 0
                    else "auto"
                )
                request = {
                    "messages": messages,
                    "model": target_model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "tools": tools,
                    "tool_choice": tool_choice,
                    "thinking": {"type": "disabled"},  # 指定函数的 tool_choice 需要关闭 thinking
                }
                post_fn = self._post_vision if use_vision_client else self._post_response
                response = await post_fn(client, request)

                # Parse Chat Completions response
                choices = response.get("choices", [])
                if not choices:
                    raise LLMAPIError("Chat Completions API returned no choices")
                message = choices[0].get("message", {})
                tool_calls = message.get("tool_calls") or []

                if not tool_calls:
                    # No tool calls — extract text content
                    if successful_tool_calls == 0:
                        raise LLMAPIError("model returned a result without successful python verification")
                    content = message.get("content", "")
                    return self.extract_json(content)

                if attempted_tool_calls + len(tool_calls) > max_tool_calls:
                    raise LLMAPIError("model exceeded the python_verify tool-call limit")

                # Add assistant message with tool calls to history
                messages.append(message)

                for call in tool_calls:
                    attempted_tool_calls += 1
                    call_id = call.get("id", "")
                    func = call.get("function", {})
                    args_raw = func.get("arguments", "{}")
                    if not isinstance(call_id, str) or not call_id:
                        raise LLMAPIError("model returned a python tool call without id")
                    result = await self._run_python_tool(
                        func.get("name"),
                        args_raw,
                        sandbox,
                    )
                    if result.get("ok") is True:
                        successful_tool_calls += 1
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

    async def _post_response(self, client: httpx.AsyncClient, request: dict[str, Any]) -> dict[str, Any]:
        """Post to Chat Completions API (replaces Responses API for DeepSeek compatibility)."""
        try:
            response = await client.post(self.chat_completions_url, json=request)
        except httpx.HTTPError as exc:
            raise LLMAPIError(f"Chat Completions API transport failed: {type(exc).__name__}") from None

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            message = self._error_message(payload)
            raise LLMAPIError(f"Chat Completions API returned HTTP {response.status_code}: {message}")
        if not isinstance(payload, dict):
            raise LLMAPIError("Chat Completions API returned a non-object JSON body")
        if payload.get("error"):
            raise LLMAPIError(f"Chat Completions API failed: {self._error_message(payload.get('error'))}")
        return payload

    async def _post_vision(self, client: httpx.AsyncClient, request: dict[str, Any]) -> dict[str, Any]:
        """Post to Vision API (SiliconFlow/Qwen3-VL)."""
        try:
            response = await client.post(self.vision_chat_completions_url, json=request)
        except httpx.HTTPError as exc:
            raise LLMAPIError(f"Vision API transport failed: {type(exc).__name__}") from None

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            message = self._error_message(payload)
            raise LLMAPIError(f"Vision API returned HTTP {response.status_code}: {message}")
        if not isinstance(payload, dict):
            raise LLMAPIError("Vision API returned a non-object JSON body")
        if payload.get("error"):
            raise LLMAPIError(f"Vision API failed: {self._error_message(payload.get('error'))}")
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
        """Extract text from Chat Completions response (choices[0].message.content)."""
        choices = response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            if content:
                return content
        # Fallback: Responses API format
        direct_text = response.get("output_text")
        if isinstance(direct_text, str) and direct_text:
            return direct_text
        raise LLMAPIError("API result does not contain output text")

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
