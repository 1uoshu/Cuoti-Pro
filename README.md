# Cuoti-Pro

智能学习错题 Agent 项目，面向中学生的作业批改、错题归档、薄弱知识点定位和分层练习。

当前迭代优先交付任务书中的场景 1 和场景 2：

- 场景 1：日常习题 / 试卷上传与自动批改
- 场景 2：薄弱知识点巩固提升

## Repository Layout

- `backend/`: FastAPI backend with a kernel-managed plugin architecture.
- `frontend/`: Vue 3 frontend.
- `docs/`: project-level architecture decisions and glossary.
- `reports/`: presentation and progress report artifacts.
- `CONTEXT.md`: shared domain language for the team.

## Backend Architecture

The backend uses a kernel-managed plugin architecture:

- Kernel capabilities: auth, config, database, audit logging, background jobs, LLM gateway, Agent runtime, RAG, knowledge graph, file storage, and plugin loading.
- Plugin capabilities: assignment grading, wrong question book, mastery tracking, layered practice, dashboard composition, and example plugin.

See `backend/docs/plugin-development.md` for backend contributor rules.
Frontend developers should read `API接口文档.md` and `docs/frontend-integration-security.md` before wiring pages.

## Branch Strategy

- `main`: stable submission/demo branch.
- `develop`: integration branch for day-to-day collaboration.
- `role/agent-design`: Agent workflow, prompts, LLM gateway, RAG, knowledge graph.
- `role/backend-core`: kernel, plugin system, auth, database, shared infrastructure.
- `role/backend-feature`: business plugins and backend API implementation.
- `role/frontend-app`: frontend pages, routing, API integration.
- `role/frontend-ui`: UI polish, visualization, responsiveness.
- `role/testing-docs`: tests, test report, API docs, deployment docs, final review.

## Quick Start

Backend and MySQL with Docker Compose:

```bash
cp .env.compose.example .env
# Fill in OPENAI_API_KEY and replace the demo secrets.
docker compose up --build -d
```

The backend starts at `http://localhost:8000`; this Compose delivery intentionally does
not build or modify the frontend. See `backend/docs/deployment.md` for health checks,
persistence, and production notes.

Local backend development:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Local frontend development:

```bash
cd frontend
npm install
npm run dev
```
