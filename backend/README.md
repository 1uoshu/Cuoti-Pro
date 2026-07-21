# Smart Learning Agent Backend

FastAPI backend for the Smart Learning Agent project. The codebase is organized as a kernel-managed plugin system: shared infrastructure belongs to the kernel, and learning scenarios live in plugins.

## Local setup

1. Copy `.env.example` to `.env`.
2. Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` for the GPT-5.5 gateway.
3. Install dependencies:

   ```bash
   uv sync
   ```

4. Run the API:

   ```bash
   uv run uvicorn app.main:app --reload --port 8000
   ```

The API documentation is available at `http://localhost:8000/docs`.

## Architecture

- `app/kernel`: application startup, configuration, database, audit logging, background jobs, auth, LLM gateway, Agent runtime, RAG and knowledge graph interfaces, plugin loading, and response envelopes.
- `app/plugins`: business capabilities loaded by the kernel at startup.
- `app/plugins/example`: reference plugin for backend developers.
- `docs/plugin-development.md`: plugin rules and extension guide.
- `docs/api.md`: frontend-facing API summary.

## Current plugins

- `example`: documents the plugin contract.
- `mastery_tracking`: knowledge points and mastery records.
- `wrong_question_book`: wrong question archive.
- `assignment_grading`: homework upload, multimodal grading, and manual correction.
- `layered_practice`: weak-point practice generation and submission grading.
- `learning_dashboard`: composed student dashboard.

## Tests

```bash
uv run pytest
```
