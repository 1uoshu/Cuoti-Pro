import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from app.kernel.config import Settings


class LLMGateway:
    """Kernel-owned OpenAI-compatible model gateway."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def _client(self) -> AsyncOpenAI:
        self._settings.validate_model_config()
        return AsyncOpenAI(api_key=self._settings.openai_api_key, base_url=self._settings.openai_base_url)

    @property
    def model(self) -> str:
        return self._settings.openai_model

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

    async def chat_json(self, system_prompt: str, user_prompt: str, *, temperature: float, max_tokens: int) -> dict[str, Any]:
        response = await self._client().chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return self.extract_json(response.choices[0].message.content or "")

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
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
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
        response = await self._client().chat.completions.create(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        *[
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                            for image_data_url in image_data_urls
                        ],
                    ],
                },
            ],
        )
        return self.extract_json(response.choices[0].message.content or "")

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
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        *[
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                            for image_data_url in image_data_urls
                        ],
                    ],
                },
            ],
            sandbox,
            temperature=temperature,
            max_tokens=max_tokens,
            max_tool_calls=max_tool_calls,
        )

    async def _json_with_python(
        self,
        messages: list[dict[str, Any]],
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
                        "additionalProperties": False,
                    },
                },
            }
        ]
        used_tool_calls = 0
        client = self._client()

        while True:
            response = await client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            tool_calls = list(message.tool_calls or [])
            if not tool_calls:
                return self.extract_json(message.content or "")
            if used_tool_calls + len(tool_calls) > max_tool_calls:
                raise ValueError("model exceeded the python_verify tool-call limit")

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                used_tool_calls += 1
                result = await self._run_python_tool(call.function.name, call.function.arguments, sandbox)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

    @staticmethod
    async def _run_python_tool(name: str, arguments: str, sandbox: Any) -> dict[str, Any]:
        if name != "python_verify":
            return {"ok": False, "value": None, "error": f"unknown tool: {name}"}
        try:
            payload = json.loads(arguments)
            code = payload["code"]
            if not isinstance(code, str):
                raise TypeError("code must be a string")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            return {"ok": False, "value": None, "error": f"invalid tool arguments: {exc}"}

        execution = await asyncio.to_thread(sandbox.execute, code)
        return {"ok": execution.ok, "value": execution.value, "error": execution.error}
