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

    async def vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_data_url: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
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
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
        )
        return self.extract_json(response.choices[0].message.content or "")
