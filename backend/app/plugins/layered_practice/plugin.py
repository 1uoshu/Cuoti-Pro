from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.layered_practice import models  # noqa: F401 - registers ORM models
from app.plugins.layered_practice.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="layered_practice",
        version="0.1.0",
        description="Generates layered practice questions and grades submitted practice answers.",
        routers=(router,),
        dependencies=("assignment_grading", "mastery_tracking", "wrong_question_book"),
        capabilities=("practice_generation", "practice_grading", "mastery_feedback"),
    )
