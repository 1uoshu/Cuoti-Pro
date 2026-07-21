# Frontend Notes

Frontend API details are documented in `../backend/docs/api.md`.

Before implementing pages, read `../docs/frontend-integration-security.md`. Treat all OCR, Agent, RAG, user profile, filename, question, answer, explanation, and suggestion text as untrusted input. Do not render those fields with `v-html` unless the content is sanitized first.
