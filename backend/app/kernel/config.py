from functools import lru_cache
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Learning Agent API"
    app_env: str = "development"
    database_url: str = "sqlite:///./storage/smart_learning_agent.db"
    jwt_secret_key: str = "development-only-change-me"
    jwt_expire_hours: int = 12
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = ""
    agent_api_base_url: str = ""
    agent_api_key: str = ""
    agent_api_timeout_seconds: float = 120
    max_upload_mb: int = 10
    max_pdf_pages: int = 10
    cors_origins: str = "http://localhost:5173"
    storage_dir: str = "storage"
    review_confidence_threshold: float = 0.85
    sandbox_timeout_seconds: float = 2
    sandbox_memory_limit_mb: int = 256
    sandbox_max_code_chars: int = 8_000
    sandbox_max_output_chars: int = 8_000
    auto_create_tables: bool = True
    plugin_modules: str = (
        "app.plugins.example,"
        "app.plugins.mastery_tracking,"
        "app.plugins.wrong_question_book,"
        "app.plugins.assignment_grading,"
        "app.plugins.layered_practice,"
        "app.plugins.learning_dashboard"
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
        if self.agent_api_base_url:
            parsed = urlparse(self.agent_api_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise RuntimeError("AGENT_API_BASE_URL 必须是有效的 HTTP(S) 地址")
            if not self.agent_api_key:
                raise RuntimeError("配置 AGENT_API_BASE_URL 时必须同时设置 AGENT_API_KEY")
        if self.agent_api_timeout_seconds <= 0:
            raise RuntimeError("AGENT_API_TIMEOUT_SECONDS 必须大于 0")
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
        if self.openai_base_url:
            parsed = urlparse(self.openai_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise RuntimeError("OPENAI_BASE_URL 必须是有效的 HTTP(S) 地址")


@lru_cache
def get_settings() -> Settings:
    return Settings()
