from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.wrong_question_book import models  # noqa: F401 - registers ORM models
from app.plugins.wrong_question_book import feedback_models  # noqa: F401 - registers QuestionFeedback
from app.plugins.wrong_question_book.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="wrong_question_book",
        version="0.1.0",
        description="Archives wrong questions and exposes the student's wrong question book.",
        routers=(router,),
        dependencies=("mastery_tracking",),
        capabilities=("wrong_question_archive", "recent_mistakes", "question_feedback"),
    )
