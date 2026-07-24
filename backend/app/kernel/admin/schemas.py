from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class RuntimeConfigUpdateRequest(BaseModel):
    openai_api_key: str | None = Field(default=None, min_length=1, max_length=512)
    openai_base_url: HttpUrl | None = None
    openai_model: str | None = Field(default=None, min_length=1, max_length=128)
    openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] | None = None
    openai_disable_response_storage: bool | None = None
    openai_timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    max_upload_mb: int | None = Field(default=None, ge=1, le=100)
    max_pdf_pages: int | None = Field(default=None, ge=1, le=100)
    review_confidence_threshold: float | None = Field(default=None, ge=0, le=1)
    token_refresh_threshold_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    pow_challenge_ttl_seconds: int | None = Field(default=None, ge=10, le=3600)
    pow_difficulty: int | None = Field(default=None, ge=0, le=12)
