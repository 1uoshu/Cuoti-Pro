from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.learning_dashboard.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="learning_dashboard",
        version="0.1.0",
        description="Composes assignment, wrong-question, and mastery data for the student dashboard.",
        routers=(router,),
        dependencies=("assignment_grading", "wrong_question_book", "mastery_tracking"),
        capabilities=("student_dashboard",),
    )
