# Built-in Agent Design

Status: demo implementation for task-book scenes 1 and 2.

## Ownership

The Agent runs inside this backend. It reuses `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and
`OPENAI_MODEL`; no second Agent service or key is required.

The kernel owns shared infrastructure:

- `LLMGateway`: raw HTTP OpenAI Responses requests for text, images, and bounded tool calls;
- `AgentRuntime`: LangGraph workflow construction;
- `PythonSandbox`: the `execute(code) -> SandboxResult` verification interface;
- authentication, persistence, uploads, audit, jobs, RAG, and knowledge-graph interfaces.

Plugins own learning behavior and prompts. They obtain capabilities only through
`KernelContext`; they do not create model clients or sandbox processes.

The Responses adapter extracts text from `output[].content[].output_text`, sends images as
`input_image` data URLs, consumes `function_call` items, and returns sandbox results as
`function_call_output`. Provider errors are bounded and never include the configured key.

## Scene 1: Assignment Grading

```text
image/PDF upload
  -> background task
  -> render every PDF page
  -> multimodal grading Agent
  -> python_verify for calculable math/physics questions
  -> Pydantic validation
  -> per-question result + confidence warning
  -> wrong-question book + mastery + audit log
```

Different correct derivations are allowed. For derivatives and integrals, the prompt asks
the Agent to test mathematical equivalence and domains instead of comparing expression
strings or requiring the same SymPy form.

## Scene 2: Layered Practice

```text
weak point + difficulty + recent mistakes
  -> LangGraph prepare_context
  -> generate with python_verify
  -> validate count, uniqueness, answer and confidence
  -> persist practice
  -> immediate answer grading with python_verify
  -> confidence warning + mastery update + audit log
```

The four levels are `基础补漏`, `同类变式`, `综合提升`, and `高考真题`.

## Correctness Policy

`python_verify` allows `math`, `statistics`, `fractions`, `decimal`, `sympy`, and `pint`.
For applicable questions, prompts require checks such as:

- symbolic equivalence after simplification;
- domain, excluded values, endpoint, and solution-set checks;
- numeric sampling away from singularities;
- physical units and dimensional consistency;
- option completeness and uniqueness.

The tool is evidence, not an oracle. SymPy output is not treated as the required human
solution. If OCR, formalization, or deterministic verification is insufficient, the Agent
still returns a result with lower `confidence`; the API adds `confidence_warning` and lets
the user decide. There is no blocking human-review state.

## Demo Sandbox Boundary

The demo uses AST validation, RestrictedPython, an isolated child process, a sanitized
environment, import/name restrictions, execution timeout, output limits, and CPU/memory
limits where the operating system supports them. Docker also drops Linux capabilities,
sets `no-new-privileges`, limits PIDs, and provides a bounded temporary filesystem.

RestrictedPython is not a production-grade hostile-code isolation boundary. Before a
public deployment that accepts adversarial code, replace the current adapter with a
dedicated container or micro-VM worker with no application secrets, no network, a
read-only filesystem, seccomp/AppArmor, per-call cgroups, and process recycling. The
plugin interface can remain unchanged.
