from fastapi import APIRouter, Depends

from app.kernel.auth.dependencies import get_current_user
from app.kernel.context import get_kernel_context
from app.kernel.models import User
from app.kernel.responses import ok


router = APIRouter(prefix="/example", tags=["example-plugin"])


@router.get("/ping")
def ping():
    return ok({"plugin": "example", "status": "ok"})


@router.get("/capabilities")
def capabilities(_: User = Depends(get_current_user)):
    context = get_kernel_context()
    return ok(
        {
            "message": "This plugin demonstrates the allowed plugin surface.",
            "allowed": [
                "declare metadata through PluginSpec",
                "register FastAPI routers under /api",
                "call kernel capabilities through KernelContext",
                "depend on another plugin by name",
            ],
            "not_allowed": [
                "create a separate database engine",
                "own global authentication or middleware",
                "call LLM/RAG/knowledge graph adapters directly instead of the kernel",
                "mutate another plugin's private implementation details",
            ],
            "kernel_capabilities": {
                "database": type(context.capabilities.database).__name__,
                "jobs": type(context.capabilities.jobs).__name__,
                "llm": type(context.capabilities.llm).__name__,
                "agent_runtime": type(context.capabilities.agent_runtime).__name__,
                "rag": type(context.capabilities.rag).__name__,
                "knowledge_graph": type(context.capabilities.knowledge_graph).__name__,
                "storage": type(context.capabilities.storage).__name__,
                "redis": type(context.capabilities.redis).__name__,
            },
        }
    )
