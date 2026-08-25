# Backend Implementation — Recruitment Assistant

**Persona**: @backend-eng | **Action**: `*develop-be` (includes `*define-agents`, `*implement-endpoint`,
`*document-backend`) | **Status**: MVP implemented

## Input Requirements

**PRD**: `project-context/1.define/prd.md` (Draft v1, revised 2026-08-20 — 3-agent design)
**SAD**: `project-context/1.define/sad.md` (Draft v2, revised 2026-08-20 — 3-agent design, FastAPI fixed)
**setup.md**: `project-context/2.build/setup.md` — **does not exist**. `@project.mgr`'s `*setup-project`
was not run for this project (`project-context/2.build/` contained only `.gitkeep` at the start of this
session). Per `aamad-core.mdc` ("On missing/ambiguous inputs, write Assumptions and Open Questions; do not
fabricate content") this is recorded as an Assumption below rather than blocking: PRD and SAD were already
complete and specific enough (agent design, API contract, tool set, framework choice) to scaffold the
backend directly. No repo-wide scaffolding decisions (e.g. monorepo layout, frontend tooling) were made by
this persona — only the `backend/` subtree.
**Runtime**: `crewai`, resolved from `aamad.config.yml` → `runtime.target: crewai` (no
`AAMAD_TARGET_RUNTIME` env var override observed). See Audit.

## What Was Built

### Directory layout

```
backend/
  app/
    __init__.py
    main.py          FastAPI app: /health, POST /api/runs, GET /api/runs/{run_id}
    models.py         Pydantic request/response models (JobRequisition, RunResultResponse, ...)
    run_store.py       In-memory run store (pending/running/succeeded/failed), thread-safe
    trace_log.py        Trace Log writer -> project-context/2.build/logs/{run_id}.jsonl, secret-redacted
    crew.py             CrewBase RecruitmentCrew (researcher -> evaluator -> recommender) + run_crew()
    config/
      agents.yaml        3 agent definitions (role/goal/backstory/allow_delegation)
      tasks.yaml         3 task definitions (description/expected_output/agent/context)
  tests/
    test_config.py       Validates agents.yaml/tasks.yaml shape, no LinkedIn tool, context chain
    test_crew_module.py  Static regression guard: crew.py has no LinkedIn tool, uses Process.sequential
    test_api.py           FastAPI integration tests (422 validation, full run lifecycle, error envelope)
  requirements.txt
```

Root-level changes: `.env.example` gained a `SERPER_API_KEY` entry; `.gitignore` gained rules to keep
generated Trace Log files (`project-context/2.build/logs/*.jsonl`) and Python/venv/pytest artifacts out of
version control.

### Agents (`config/agents.yaml`) — SAD §2

Three agents, `allow_delegation: false` on each, no memory, matching SAD's table exactly:

| Agent | Role | Tools |
|---|---|---|
| `researcher` | Job Candidate Researcher | `SerperDevTool`, `ScrapeWebsiteTool` |
| `evaluator` | Candidate Evaluator and Scorer | `SerperDevTool`, `ScrapeWebsiteTool` |
| `recommender` | Candidate Recommendation and Outreach Strategist | `SerperDevTool`, `ScrapeWebsiteTool` |

No `LinkedInTool` (or equivalent) is bound to any agent — enforced by `crew.py`'s single shared
`_tools()` helper and guarded by both `tests/test_config.py` and `tests/test_crew_module.py`.

### Tasks (`config/tasks.yaml`) — SAD §2, §4

`research_candidates_task` → `evaluate_and_score_candidates_task` → `recommend_candidates_task`, chained
via `Task.context` (the final task's `context` lists both prior task ids, per SAD's 2-item context list).
The final task's `expected_output` requires exactly two headings, `## Recommendations` and
`## Outreach Guidance`, matching PRD FR-4's merged-report requirement.

Every field of `JobRequisition` (`job_title`, `job_description`, `responsibilities`, `requirements`,
`preferred_qualifications`, `perks`, `candidate_count`) is referenced by at least one task's
`description`/`expected_output` — `tests/test_config.py::test_every_requisition_field_is_used_by_at_least_one_task`
guards this as a regression. (`perks` was initially missing from both `research_candidates_task` and
`recommend_candidates_task` — passed through in `main.py`'s `inputs` dict but never interpolated into any
prompt, so it was silently dropped from the pipeline; fixed during review.)

### Crew entrypoint (`app/crew.py`)

`RecruitmentCrew` (`@CrewBase`) wires the 3 agents/3 tasks into a `Crew` with `Process.sequential`,
`memory=False`, and crew-level `max_rpm=20`. Per-task/agent controls follow the adapter rule baseline:
`max_iter=12`, `max_retry_limit=2`. `run_crew(inputs)` calls `crew.kickoff(inputs=...)` and returns the
final report as a string; this is the single seam the API layer calls into.

### API (`app/main.py`) — SAD §4

- `GET /health` → `{"status": "ok"}` (SAD §5 operational sanity check).
- `POST /api/runs` → validates the requisition via the `JobRequisition` Pydantic model (title +
  description required; responsibilities/requirements/preferred_qualifications/perks optional;
  `candidate_count` defaults to 10, bounded 1–25 per PRD's cost-control note), creates a run record, and
  schedules `run_crew` on a FastAPI `BackgroundTasks` task — returns `202` with `{run_id, status: pending}`
  immediately rather than blocking on the multi-minute pipeline, per SAD §4's async job pattern decision.
- `GET /api/runs/{run_id}` → returns `{run_id, status, created_at, updated_at, report, error}`. `404` if
  unknown. On pipeline failure, `error` is `{"code": "pipeline_error", "message": "..."}`, matching SAD
  §4's custom error envelope for run-failure states.
- Missing required fields on submission → FastAPI's default `422` validation response (SAD §4).
- CORS is open (`allow_origins=["*"]`) since there is no deployed frontend origin yet and no
  authentication at MVP scope (PRD §5, SAD §8) — revisit if ever exposed beyond localhost.

### Run state (`app/run_store.py`)

In-memory only, thread-locked dict of `run_id -> RunRecord`, per SAD §4 Data Architecture ("None for
MVP... may live in-process/in-memory only"). State is lost on process restart — acceptable per PRD's
stateless-run design.

### Logging (`app/trace_log.py`)

Writes one append-only JSONL Trace Log per run to `project-context/2.build/logs/{run_id}.jsonl` (event:
`run_submitted` / `run_started` / `run_succeeded` / `run_failed`), with a best-effort secret redaction
regex applied to logged detail values, per the adapter rule's "Logging" section. **Gap, recorded rather
than silently omitted**: no Prompt Trace (rendered system/user prompts) capture is implemented — that
would require a CrewAI step/task callback wired into the LLM call, which was judged out of scope for MVP
(not required by any PRD acceptance criterion) but is flagged as an Open Question below since the adapter
rule lists it as a requirement, not just a nice-to-have.

## Verification Performed

- `backend/requirements.txt` installed cleanly into a fresh Python 3.13 virtualenv (`crewai`, `crewai-tools`,
  and `fastapi` do not yet publish wheels for Python 3.14 — recorded as an Assumption below).
- `pytest` (15 tests, all passing): YAML config shape/contents, no-LinkedIn-tool regression guards,
  sequential/no-memory regression guard, FastAPI validation (`422`), full async run lifecycle
  (`pending → running → succeeded`, with `run_crew` stubbed per SAD §9's mocking guidance), and the
  failure path (`pending → running → failed` with the structured error envelope).
- Live smoke test: started `uvicorn app.main:app`, confirmed `GET /health` returns `200`, confirmed
  `POST /api/runs` with a missing `description` field returns `422`, and confirmed a real submitted run
  correctly reaches `status: failed` with `error.code: "pipeline_error"` when the configured
  `OPENAI_API_KEY` is invalid (this repo's `.env` currently still holds its placeholder value) —
  validates the full async submit → background-execute → poll → surfaced-error round trip end-to-end,
  including live `.env` loading. Generated Trace Log files from this manual smoke test were deleted
  afterward (not committed).
- Did **not** perform a real, fully-successful end-to-end run against live OpenAI/Serper APIs — no valid
  API keys are present in this environment. SAD §9's "one real (non-mocked) end-to-end run" smoke/acceptance
  criterion is therefore only partially satisfied (the failure path was exercised live; the success path
  was only exercised with `run_crew` stubbed). Recorded as an Open Question / QA follow-up below.

## Known Gaps / Non-MVP Stubs (per persona's `*stub-nonmvp` scope)

- No LinkedIn sourcing tool (explicit MVP exclusion, PRD §3 — not a gap, a decision).
- No outreach *send* capability — `recommender`'s output is draft-only markdown text (PRD FR-4).
- No persistence layer / database (PRD §3, §4).
- No authentication on the API (PRD §3, §5).
- No Prompt Trace capture (see Logging section above) — a genuine gap against the adapter rule, not a PRD
  requirement.
- No rate limiting / multi-run concurrency controls beyond `max_rpm` at the crew level.

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/sad.md`
- `.cursor/rules/adapter-crewai.mdc`
- `.cursor/rules/aamad-core.mdc`
- `aamad.config.yml`
- `.env.example` (pre-existing, updated with `SERPER_API_KEY`)

## Assumptions

- `project-context/2.build/setup.md` does not exist (`@project.mgr` setup was not run). Proceeded with
  backend scaffolding directly since PRD/SAD already fixed the framework (FastAPI), agent design, and API
  contract — no project-wide scaffolding decision was invented by this persona.
- CrewAI's config-path resolution convention (agent/task YAML living alongside the module that defines the
  `@CrewBase` class) was followed, placing `config/` at `backend/app/config/` rather than a bare top-level
  `backend/config/`, so that `agents_config = "config/agents.yaml"` resolves correctly relative to
  `crew.py`. This still satisfies SAD §2/§4's "externalized to `config/agents.yaml`... under the backend
  runtime package" requirement; the exact subpath was left to this persona's discretion.
- Python 3.14 (the default `python3` on this machine) is not yet supported by `crewai`/`crewai-tools`/
  `fastapi`'s published wheels; the backend `.venv` was built against Python 3.13 instead. `@devops.eng`
  should pin a Python version (e.g. via `pyproject.toml` / CI config) rather than relying on whatever
  `python3` resolves to.
- LLM provider is assumed to be OpenAI, per the pre-existing `.env.example`'s `OPENAI_API_KEY`/
  `OPENAI_MODEL` entries (PRD Open Question — not newly resolved by this persona, just inherited).
- Trace Log JSONL files are treated as generated, non-committed artifacts (added to `.gitignore`), matching
  the pattern already used for `.env`.

## Open Questions

- **Prompt Trace capture** (adapter rule requirement, not yet implemented): should `@backend.eng`/
  `@integration.eng` add a CrewAI step callback to capture rendered prompts before execution, or is
  Trace Log (lifecycle events) sufficient for this project's MVP? Not resolved here.
- **Full live success-path smoke test**: SAD §9's smoke/acceptance criterion (one real end-to-end run) was
  only partially exercised (see Verification Performed) due to lack of valid API keys in this environment.
  Should be re-run by `@qa.eng` or the operator once real `OPENAI_API_KEY`/`SERPER_API_KEY` values are in
  `.env`.
- **LLM provider/model, web-search provider** (carried from PRD/SAD, still unresolved): this backend is
  provider-agnostic at the code level (env-var driven), but the actual provider choice is still an open
  product decision.
- **Synchronous vs. async API pattern** (carried from SAD, still unresolved): implemented per SAD's async
  submit/poll default; SAD itself flags this as worth revisiting for a purely local/personal deployment.

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `backend-eng`
- **Action**: `develop-be` (`define-agents`, `implement-endpoint`, `document-backend`)
- **Resolved AAMAD_TARGET_RUNTIME**: AAMAD_TARGET_RUNTIME=crewai (from `aamad.config.yml`; no environment variable override observed)
- **Runtime controls recorded**: `Process.sequential`; `memory=False`; crew-level `max_rpm=20`; per-task
  `max_iter=12`, `max_retry_limit=2` (adapter rule baseline, unchanged — no epic-specific justification for
  deviating).
- **LLM / model**: not pinned by this persona — resolved at runtime from `OPENAI_API_KEY`/`OPENAI_MODEL`
  environment variables via CrewAI's default LLM wiring (LiteLLM under the hood); no explicit `llm=` override
  set on any agent.
- **Upstream artifacts**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`.
- **Test results**: 15/15 backend tests passing (`backend/tests/`); live smoke test of `/health`,
  `POST /api/runs` validation, and one real (failing, due to placeholder API key) run lifecycle.
