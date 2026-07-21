# Agent Service Integration Decision

Status: accepted on 2026-07-21.

## Context

The Agent team supplied `docs/agent_api.json`, an OpenAPI 3.1 contract for five Agent workflows. The current delivery scope is task-book scene 1 (assignment upload and automatic grading) and scene 2 (weak-point layered practice). The supplied contract defines request bodies but does not define a server URL, authentication scheme, or successful response schemas.

The backend already exposes stable student-facing APIs and owns authentication, persistence, audit logs, background tasks, the wrong-question book, and mastery records. Replacing those APIs with direct Agent routes would leak Agent-specific contracts into business plugins and clients.

## Decision

The kernel owns one `AgentAPIClient`, exposed to plugins through `KernelCapabilities.agent_api`.

- Configure the service with `AGENT_API_BASE_URL`, `AGENT_API_KEY`, and `AGENT_API_TIMEOUT_SECONDS`.
- Send the JWT only as `Authorization: Bearer <token>`.
- Never include the JWT in URLs, audit metadata, exception messages, or stored learning records.
- If `AGENT_API_BASE_URL` is empty, use the project-owned built-in LangGraph Agent with
  `OPENAI_*`; this is the default delivery mode.
- Business plugins keep their existing public APIs and database models.

## Scene Mapping

| Backend workflow | Agent operation | Contract mapping |
| --- | --- | --- |
| Image assignment grading | `POST /api/grade/image` | multipart `student_id`, `question`, `subject`, `image` |
| PDF assignment grading | `POST /api/grade/pdf` | multipart `student_id`, `question`, `subject`, `pdf` |
| Manual question correction | `POST /api/grade` | JSON `student_id`, `question`, `student_answer`, `subject` |
| Layered practice generation | `POST /api/practice/generate` | form `student_id`, `weak_points`, `difficulty` |
| Practice answer grading | `POST /api/practice/answer` | form `student_id`, `question_json`, `student_answer` |

Difficulty mapping is explicit: `基础补漏 -> base`, `同类变式 -> variant`, `综合提升 -> advanced`, and `高考真题 -> exam`.
The Agent contract has no `question_count` field. The adapter therefore collects and de-duplicates responses until it reaches the backend request count, with a bounded maximum of three attempts per requested question. It trims extra valid questions and fails if the requested count still cannot be met.

## Response Boundary

Because the Agent OpenAPI currently leaves every HTTP 200 response schema empty, Agent output is untrusted input. The backend accepts common wrapper keys such as `data`, `result`, and `output`, then normalizes field aliases into the existing Pydantic domain models. It rejects:

- non-object JSON;
- missing or empty question lists;
- missing question, answer, or explanation text required by the local model;
- invalid booleans, scores, confidence values, or question counts.

Assignment totals and weak points may be deterministically derived from validated per-question results. They are never invented by a second model call.

## Failure Behavior

- Network, timeout, non-JSON, HTTP error, and validation failures become explicit Agent errors.
- Assignment background tasks become `failed` and retain a bounded error message for diagnosis.
- Invalid grading output is not persisted as completed work and does not update mastery.
- Missing or low confidence returns `confidence_warning` so the user can judge the result.
  It does not create a blocking manual-review workflow.
- Practice generation remains `failed` when its result cannot satisfy the requested question count.
- The external Agent service never receives the student's backend JWT; it receives only its own configured service JWT and a non-secret student identifier.

## Task-Book And Bonus Alignment

Delivered for scenes 1 and 2:

- image and PDF upload through the documented multimodal Agent endpoints;
- full PDF forwarding instead of rendering only the first page when Agent mode is enabled;
- structured per-question grading, knowledge-point binding, wrong-question archiving, and mastery updates;
- all four layered-practice levels and immediate Agent grading;
- asynchronous assignment status, failure handling, audit events, and end-to-end tests.

Prepared but not claimed as delivered:

- the kernel knowledge-graph interface can later back an interactive visualization;
- RAG remains kernel-owned for later mistake retrieval and reranking;
- review export, Anki/PDF export, voice input, and parent subscriptions belong to later scenes or require frontend work.

This distinction keeps the scene 1/2 delivery accurate while preserving the extension points requested by the task book.
