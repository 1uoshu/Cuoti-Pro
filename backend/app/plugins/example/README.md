# Example Plugin

This plugin is the reference implementation for backend developers. Copy its shape when adding a new business plugin.

## Required Contract

Every plugin must expose a `get_plugin(context) -> PluginSpec` factory from `plugin.py`:

```python
from app.kernel.context import KernelContext
from app.kernel.plugins import PluginSpec
from app.plugins.example.routes import router


def get_plugin(_: KernelContext) -> PluginSpec:
    return PluginSpec(
        name="example",
        version="0.1.0",
        description="Reference plugin.",
        routers=(router,),
        dependencies=(),
        capabilities=("plugin_contract_documentation",),
    )
```

## Allowed Surface

- Register FastAPI routers. They will be mounted under `/api` by the kernel.
- Use `get_db` for database sessions.
- Use `get_current_user` for authenticated endpoints.
- Use `get_kernel_context()` or the injected `KernelContext` for audit logging, background jobs, LLM, Agent runtime, RAG, knowledge graph, and file storage.
- Declare plugin dependencies by name in `PluginSpec.dependencies`.

## Not Allowed

- Creating another FastAPI app or global middleware.
- Creating another SQLAlchemy engine or session factory.
- Creating a separate audit logger, audit table, or background queue.
- Implementing a separate auth system.
- Calling model, RAG, or graph providers directly.
- Reaching into another plugin's private internals instead of using a small service function.

## Demo Endpoints

- `GET /api/example/ping`: unauthenticated health check for the plugin.
- `GET /api/example/capabilities`: authenticated description of the kernel capabilities available to plugins.
