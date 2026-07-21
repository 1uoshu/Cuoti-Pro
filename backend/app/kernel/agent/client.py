from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


class AgentAPIError(RuntimeError):
    """Raised when the external Agent service cannot satisfy a request."""


class AgentAPIClient:
    """Client for the scene APIs documented in ``docs/agent_api.json``."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        *,
        api_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        self._api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._transport = transport

    async def grade_file(
        self,
        *,
        student_id: str,
        file_path: str | Path,
        question: str,
        subject: str,
    ) -> dict[str, Any]:
        path = Path(file_path)
        is_pdf = path.suffix.lower() == ".pdf"
        endpoint = "/api/grade/pdf" if is_pdf else "/api/grade/image"
        field_name = "pdf" if is_pdf else "image"
        content_type = "application/pdf" if is_pdf else _image_content_type(path)
        return await self._request(
            "POST",
            endpoint,
            data={"student_id": student_id, "question": question, "subject": subject},
            files={field_name: (path.name, path.read_bytes(), content_type)},
        )

    async def grade_text(
        self,
        *,
        student_id: str,
        question: str,
        student_answer: str,
        subject: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/grade",
            json={
                "student_id": student_id,
                "question": question,
                "student_answer": student_answer,
                "subject": subject,
            },
        )

    async def generate_practice(
        self,
        *,
        student_id: str,
        weak_points: str,
        difficulty: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/practice/generate",
            data={"student_id": student_id, "weak_points": weak_points, "difficulty": difficulty},
        )

    async def answer_practice(
        self,
        *,
        student_id: str,
        question: dict[str, Any],
        student_answer: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/practice/answer",
            data={
                "student_id": student_id,
                "question_json": json.dumps(question, ensure_ascii=False),
                "student_answer": student_answer,
            },
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.TimeoutException as error:
            raise AgentAPIError(f"Agent API request timed out: {path}") from error
        except httpx.RequestError as error:
            raise AgentAPIError(f"Agent API request failed: {error}") from error

        if response.is_error:
            raise AgentAPIError(_remote_error_message(response, self._api_key))

        try:
            payload = response.json()
        except ValueError as error:
            raise AgentAPIError("Agent API response is not valid JSON") from error
        if not isinstance(payload, dict):
            raise AgentAPIError("Agent API response must be a JSON object")
        return _unwrap_response(payload)


def _image_content_type(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(path.suffix.lower(), "application/octet-stream")


def _unwrap_response(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload
    wrappers = ("data", "result", "output", "final_answer", "response", "grade_result")
    for _ in range(10):
        for wrapper in wrappers:
            if wrapper not in current:
                continue
            nested = _decode_mapping(current[wrapper])
            if nested is None:
                raise AgentAPIError(f"Agent API response field {wrapper} must contain a JSON object")
            current = nested
            break
        else:
            return current
    raise AgentAPIError("Agent API response nesting is too deep")


def _decode_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if "```" in text:
        sections = text.split("```")
        if len(sections) >= 3:
            text = sections[1].removeprefix("json").strip()
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _remote_error_message(response: httpx.Response, api_key: str) -> str:
    detail: Any
    try:
        payload = response.json()
        detail = payload.get("message") or payload.get("detail") or payload.get("error")
    except (ValueError, AttributeError):
        detail = response.text.strip()
    if isinstance(detail, (dict, list)):
        detail = json.dumps(detail, ensure_ascii=False)
    message = f"Agent API returned HTTP {response.status_code}: {detail or response.reason_phrase}"
    return message.replace(api_key, "[REDACTED]") if api_key else message
