# Backend Plugin Development

The backend uses a kernel-managed plugin architecture. The kernel owns shared capabilities and loads feature plugins at startup.

## Kernel capabilities

- Application startup, CORS, exception handling, and the `/api` root router.
- Configuration through `.env`.
- SQLAlchemy engine, session lifecycle, and the shared declarative base.
- Background job scheduling.
- Audit logging, including event storage, redaction, and audit query routes.
- User management, JWT authentication, and current-user dependencies.
- File upload storage.
- OpenAI-compatible LLM gateway.
- LangGraph agent runtime.
- RAG and knowledge graph interfaces.
- Unified API response envelope: `{ "code": 0, "message": "success", "data": ... }`.

## Plugin responsibilities

A plugin owns one business capability. It may register routes, ORM models, schemas, serializers, and internal services. It must expose:

```python
def get_plugin(context: KernelContext) -> PluginSpec:
    return PluginSpec(...)
```

Use `app.plugins.example` as the reference shape.

## Plugin rules

- Do not create your own database engine or session factory. Use `app.kernel.database.get_db` in request handlers.
- Use `context.capabilities.database.session()` for background jobs or other non-request code paths.
- Use `context.capabilities.jobs.enqueue(...)` to schedule background work.
- Use `context.capabilities.audit.record(...)` for security, authentication, upload, grading, and practice events. Do not store passwords, tokens, or full student answers in audit metadata.
- Do not implement your own authentication. Use `app.kernel.auth.dependencies.get_current_user`.
- Do not call model providers directly. Use `context.capabilities.llm`.
- Do not call the external Agent service directly. Use `context.capabilities.agent_api`; the kernel owns its URL, JWT, timeout, and error handling.
- Do not create a separate RAG or graph connection. Use `context.capabilities.rag` and `context.capabilities.knowledge_graph`.
- Keep plugin `__init__.py` lightweight. Do not import routes, services, or models there.
- Put user-facing routes in `routes.py`, business behavior in `service.py`, persistence models in `models.py`, and wire metadata in `plugin.py`.
- Declare plugin dependencies by name in `PluginSpec.dependencies`.

## Current kernel routes

- `/api/audit-logs/me`: user-visible audit history backed by the kernel audit logger.

## Current plugins

- `example`: reference plugin for backend developers.
- `mastery_tracking`: knowledge points, mastery records, and dashboard weak points.
- `wrong_question_book`: wrong question archive and recent mistakes.
- `assignment_grading`: upload, multimodal grading, and question review.
- `layered_practice`: layered practice generation, submission, and mastery feedback.
- `learning_dashboard`: composition plugin for the student dashboard.

## Adding a new plugin

1. Create a folder under `app/plugins/<plugin_name>/`.
2. Keep `__init__.py` as a short docstring only.
3. Add `models.py` only if the plugin owns database tables.
4. Add `schemas.py` for request and model-output contracts.
5. Add `service.py` for business behavior.
6. Add `routes.py` for FastAPI routes.
7. Add `plugin.py` with `get_plugin(context) -> PluginSpec`.
8. Add the package name to `PLUGIN_MODULES`.
9. Add or update tests for the plugin's public behavior.
