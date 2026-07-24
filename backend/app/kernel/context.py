from __future__ import annotations

from dataclasses import dataclass

from app.kernel.agent import AgentRuntime, PythonSandbox
from app.kernel.audit import AuditLogger
from app.kernel.config import Settings, get_settings
from app.kernel.database import DatabaseSessions
from app.kernel.jobs import JobRunner
from app.kernel.knowledge_graph import KnowledgeGraphService
from app.kernel.llm import LLMGateway
from app.kernel.rag import RAGService
from app.kernel.redis import RedisStore, build_redis_client
from app.kernel.storage import UploadStorage


@dataclass(frozen=True)
class KernelCapabilities:
    audit: AuditLogger
    database: DatabaseSessions
    jobs: JobRunner
    llm: LLMGateway
    agent_runtime: AgentRuntime
    sandbox: PythonSandbox
    rag: RAGService
    knowledge_graph: KnowledgeGraphService
    storage: UploadStorage
    redis: RedisStore


@dataclass(frozen=True)
class KernelContext:
    settings: Settings
    capabilities: KernelCapabilities


_context: KernelContext | None = None


def build_kernel_context(settings: Settings | None = None) -> KernelContext:
    resolved_settings = settings or get_settings()
    return KernelContext(
        settings=resolved_settings,
        capabilities=KernelCapabilities(
            audit=AuditLogger(),
            database=DatabaseSessions(),
            jobs=JobRunner(),
            llm=LLMGateway(resolved_settings),
            agent_runtime=AgentRuntime(),
            sandbox=PythonSandbox(
                timeout_seconds=resolved_settings.sandbox_timeout_seconds,
                memory_limit_mb=resolved_settings.sandbox_memory_limit_mb,
                max_code_chars=resolved_settings.sandbox_max_code_chars,
                max_output_chars=resolved_settings.sandbox_max_output_chars,
            ),
            rag=RAGService(),
            knowledge_graph=KnowledgeGraphService(),
            storage=UploadStorage(resolved_settings),
            redis=build_redis_client(
                resolved_settings.redis_url,
                test_mode=resolved_settings.app_env.lower() == "test",
            ),
        ),
    )


def set_kernel_context(context: KernelContext) -> None:
    global _context
    _context = context


def get_kernel_context() -> KernelContext:
    global _context
    if _context is None:
        _context = build_kernel_context()
    return _context
