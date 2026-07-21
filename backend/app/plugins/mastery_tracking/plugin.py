from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.mastery_tracking import models  # noqa: F401 - registers ORM models
from app.plugins.mastery_tracking.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="mastery_tracking",
        version="0.1.0",
        description="Tracks knowledge points and mastery records.",
        routers=(router,),
        capabilities=("mastery_records", "knowledge_points"),
    )
