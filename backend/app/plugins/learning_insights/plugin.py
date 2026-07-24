from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.learning_insights import models  # noqa: F401 - registers ORM models
from app.plugins.learning_insights.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="learning_insights",
        version="0.1.0",
        description="Builds review reports and long-term learning insights.",
        routers=(router,),
        dependencies=("assignment_grading", "wrong_question_book", "mastery_tracking", "layered_practice", "stage_assessment"),
        capabilities=("review_reports", "learning_tracking", "profile_statistics", "profile_preferences"),
    )
