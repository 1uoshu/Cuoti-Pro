# Scene 1 And 2 Evaluation

## Automated Evidence

The test suite covers:

- backend HTTP completion of assignment grading and layered practice;
- external Agent request/response normalization and JWT handling;
- built-in LangGraph workflow nodes;
- every page of a multi-page PDF reaching the multimodal model;
- bounded `python_verify` tool calls;
- allowed math libraries, rejected dangerous names, and timeout behavior;
- low-confidence results returning a warning without blocking the workflow;
- score normalization, wrong-question archiving, and mastery updates.

Run with `uv run pytest` from `backend/`.

## Required Real-Sample Evaluation

The task-book evidence should include at least three real assignment samples. They are not
stored in this repository and must not be fabricated. For each supplied sample, record:

| Sample           | Format/pages | Subject | Question recall | Grading agreement | Low-confidence warnings | Notes |
| ---------------- | ------------ | ------- | --------------: | ----------------: | ----------------------: | ----- |
| Pending sample 1 |              |         |                 |                   |                         |       |
| Pending sample 2 |              |         |                 |                   |                         |       |
| Pending sample 3 |              |         |                 |                   |                         |       |

Recommended measures:

- question recall: recognized questions / actual questions;
- grading agreement: matching correctness decisions / independently checked decisions;
- answer validity: verified generated questions / generated questions;
- warning recall: genuinely ambiguous items that received a low-confidence warning;
- latency: upload-to-completed and practice-generation elapsed time.

Do not claim production accuracy from synthetic unit tests. Preserve anonymized model
responses, tool evidence, expected decisions, and failure cases as review artifacts.
