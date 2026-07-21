from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.example.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="example",
        version="0.1.0",
        description="Reference plugin that documents the allowed plugin contract.",
        routers=(router,),
        category="reference",
        capabilities=("plugin_contract_documentation",),
        metadata={
            "owner": "backend-team",
            "purpose": "Copy this shape when creating a new feature plugin.",
        },
    )
