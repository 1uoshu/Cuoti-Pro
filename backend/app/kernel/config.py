from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Learning Agent API"
    app_env: str = "development"
    database_url: str = "sqlite:///./storage/smart_learning_agent.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret_key: str = "development-only-change-me"
    jwt_expire_hours: int = 12
    token_refresh_threshold_minutes: int = 60
    pow_challenge_ttl_seconds: int = 120
    pow_difficulty: int = 4
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = ""
    openai_fast_model: str = ""  # 轻量模型（意图分流/决策用）
    # 视觉模型（独立配置，用于批改等多模态任务）
    vision_api_key: str = ""
    vision_base_url: str = "https://api.siliconflow.cn/v1"
    vision_model: str = "Qwen/Qwen3-VL-32B-Instruct"
    openai_reasoning_effort: str = "xhigh"
    openai_disable_response_storage: bool = True
    openai_timeout_seconds: float = 120
    vision_api_key: str = ""
    vision_base_url: str = ""
    vision_model: str = ""
    max_upload_mb: int = 10
    max_pdf_pages: int = 10
    cors_origins: str = "http://localhost:5173,http://localhost:5174"
    storage_dir: str = "storage"
    review_confidence_threshold: float = 0.85
    sandbox_timeout_seconds: float = 2
    sandbox_memory_limit_mb: int = 256
    sandbox_max_code_chars: int = 8_000
    sandbox_max_output_chars: int = 8_000
    auto_create_tables: bool = True
    rate_limit_per_ip: int = 120
    rate_limit_per_user: int = 60
    rate_limit_upload: int = 10
    rate_limit_window_seconds: int = 60
    plugin_modules: str = (
        "app.plugins.example,"
        "app.plugins.mastery_tracking,"
        "app.plugins.wrong_question_book,"
        "app.plugins.assignment_grading,"
        "app.plugins.agent_chat,"
        "app.plugins.layered_practice,"
        "app.plugins.stage_assessment,"
        "app.plugins.learning_dashboard,"
        "app.plugins.learning_insights"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def plugin_module_list(self) -> list[str]:
        return [module.strip() for module in self.plugin_modules.split(",") if module.strip()]

    def validate_startup_config(self) -> None:
        if self.app_env.lower() in {"production", "prod"} and self.jwt_secret_key == "development-only-change-me":
            raise RuntimeError("生产环境必须设置独立的 JWT_SECRET_KEY")
        if not 0 <= self.review_confidence_threshold <= 1:
            raise RuntimeError("REVIEW_CONFIDENCE_THRESHOLD 必须在 0 到 1 之间")
        if self.jwt_expire_hours <= 0 or self.token_refresh_threshold_minutes < 0:
            raise RuntimeError("JWT_EXPIRE_HOURS 必须大于 0，TOKEN_REFRESH_THRESHOLD_MINUTES 不能小于 0")
        if self.pow_challenge_ttl_seconds <= 0 or not 0 <= self.pow_difficulty <= 12:
            raise RuntimeError("POW_CHALLENGE_TTL_SECONDS 必须大于 0，POW_DIFFICULTY 必须在 0 到 12 之间")
        if (
            self.sandbox_timeout_seconds <= 0
            or self.sandbox_memory_limit_mb <= 0
            or self.sandbox_max_code_chars <= 0
            or self.sandbox_max_output_chars <= 0
        ):
            raise RuntimeError("SANDBOX_* 限制必须大于 0")

    def validate_model_config(self) -> None:
        if not self.openai_api_key or self.openai_api_key.startswith("your-"):
            raise RuntimeError("未配置有效的 OPENAI_API_KEY，无法调用真实模型")
        if not self.openai_model:
            raise RuntimeError("未配置 OPENAI_MODEL，无法调用真实模型")
        if self.openai_reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
            raise RuntimeError("OPENAI_REASONING_EFFORT 不是有效值")
        if self.openai_timeout_seconds <= 0:
            raise RuntimeError("OPENAI_TIMEOUT_SECONDS 必须大于 0")
        if self.openai_base_url:
            parsed = urlparse(self.openai_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise RuntimeError("OPENAI_BASE_URL 必须是有效的 HTTP(S) 地址")

    @property
    def effective_fast_model(self) -> str:
        """快速模型（意图分流/决策），未配置时回退到主模型"""
        return self.openai_fast_model or self.openai_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
