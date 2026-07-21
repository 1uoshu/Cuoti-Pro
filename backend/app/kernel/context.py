from __future__ import annotations

from dataclasses import dataclass

from app.kernel.agent import AgentRuntime
from app.kernel.audit import AuditLogger
from app.kernel.config import Settings, get_settings
from app.kernel.database import DatabaseSessions
from app.kernel.jobs import JobRunner
from app.kernel.knowledge_graph import KnowledgeGraphService
from app.kernel.llm import LLMGateway
from app.kernel.rag import RAGService
from app.kernel.storage import UploadStorage


@dataclass(frozen=True)
class KernelCapabilities:
    audit: AuditLogger
    database: DatabaseSessions
    jobs: JobRunner
    llm: LLMGateway
    agent_runtime: AgentRuntime
    rag: RAGService
    knowledge_graph: KnowledgeGraphService
    storage: UploadStorage


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
            rag=RAGService(),
            knowledge_graph=KnowledgeGraphService(),
            storage=UploadStorage(resolved_settings),
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
