from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.stage_assessment import models  # noqa: F401 - registers ORM models
from app.plugins.stage_assessment.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="stage_assessment",
        version="0.1.0",
        description="Generates and grades stage assessment exams.",
        routers=(router,),
        dependencies=("layered_practice", "mastery_tracking"),
        capabilities=("exam_generation", "exam_grading", "score_comparison"),
    )
