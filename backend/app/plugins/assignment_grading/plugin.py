from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.assignment_grading import models  # noqa: F401 - registers ORM models
from app.plugins.assignment_grading.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="assignment_grading",
        version="0.1.0",
        description="Uploads homework, runs multimodal grading, and persists structured grading results.",
        routers=(router,),
        dependencies=("mastery_tracking", "wrong_question_book"),
        capabilities=("assignment_upload", "grading_workflow", "question_review"),
    )
