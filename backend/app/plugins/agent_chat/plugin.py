from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.agent_chat import models  # noqa: F401 - registers ORM models
from app.plugins.agent_chat.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="agent_chat",
        version="0.1.0",
        description="Agent chat sessions, messages, unified file+text upload, and review confirmation.",
        routers=(router,),
        dependencies=("assignment_grading", "wrong_question_book"),
        capabilities=(
            "session_management",
            "message_history",
            "unified_upload",
            "review_confirm",
            "replay",
        ),
    )
