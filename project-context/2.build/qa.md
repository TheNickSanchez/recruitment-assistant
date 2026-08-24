# QA Report — Recruitment Assistant

**Persona**: @qa.eng | **Actions**: `*test-unit`, `*test-integration`, `*qa`, `*verify-flow`, `*log-defects`, `*future-work` | **Status**: Conditional pass (failure path verified; live success path blocked)

**MVP verdict**: The implemented chat/recruitment flow is **acceptable to proceed to `@security.eng`** with explicitly scoped known gaps. FR-1’s submit → poll → error-surfacing round trip works end-to-end (API and UI). FR-2/FR-3/FR-4 **success** content (real candidate list, scores, two-section report) is covered by config/unit checks and a **mocked** API lifecycle only — not by a live OpenAI/Serper run.

No `AC-*` IDs exist (`system-description.md` and `user-stories` were never produced). All mapping below uses PRD **FR-1…FR-4**.

## Input Requirements

| Input | Status |
|---|---|
| `project-context/1.define/prd.md` | Present (Draft v1, revised 2026-08-20 — 3-agent design) |
| `project-context/1.define/sad.md` | Present (Draft v2 — FastAPI, async submit/poll) |
| `project-context/2.build/frontend.md` | Present |
| `project-context/2.build/backend.md` | Present |
| `project-context/2.build/integration.md` | Present |
| `project-context/1.define/system-description.md` | **Missing** — not blocking; PRD FR-1…FR-4 used as acceptance criteria |
| `project-context/1.define/user-stories` | **Missing** — not blocking |
| `project-context/2.build/setup.md` | **Missing** (same gap recorded by FE/BE/integration) — not blocking for QA |
| `aamad.config.yml` | Present — `testing.require_unit_tests: true`, `require_integration_tests: true`, `map_to_acceptance_criteria: true`, `security.require_security_assessment: true` |
| Selected runtime | `crewai` (from `aamad.config.yml` → `runtime.target`; no `AAMAD_TARGET_RUNTIME` env override in this QA session) |

## Traceability (FR → tests)

| ID | Acceptance (PRD §4) | Unit | Integration (mocked crew) | Smoke / verify-flow (live) |
|---|---|---|---|---|
| **FR-1** | Operator submits a requisition in chat; 3-agent pipeline starts; final report returns without mid-stage intervention | YAML placeholders for every `JobRequisition` field; FastAPI `422` on missing/empty required fields and out-of-range `candidate_count` (live) | `POST /api/runs` → `202` `{run_id, status: pending}`; poll `GET /api/runs/{run_id}` to `succeeded` (stubbed report) | **Pass (start + poll)**. Chat submit starts a run; statuses `pending`/`running` observed. Live run does **not** reach `succeeded` (see Gaps). |
| **FR-2** | Researcher returns a bounded candidate list (default 10) via web search/scrape only (no LinkedIn) | 3 agents / 3 tasks; no `LinkedInTool`; research task `expected_output` includes `{candidate_count}` | Not asserted at crew-output level (entire `run_crew` is stubbed) | **Partial**. Live crew log showed `research_candidates_task` start with “Find up to 10 potential candidates” and the submitted requisition fields interpolated. Task then failed at the LLM call. No real candidate list produced. |
| **FR-3** | Evaluator produces a ranked, scored, justified list; no direct LinkedIn scrape | Evaluator task `expected_output` (0–100 score + justification); LinkedIn regression guards | Not asserted at crew-output level | **Not reached live** (pipeline died in researcher). |
| **FR-4** | One markdown report with recommendations **and** outreach guidance; draft-only, no send | Final task requires `## Recommendations` and `## Outreach Guidance`; 2-item `Task.context` chain | Stubbed success report must contain both headings | **Partial**. Mocked API test asserts both headings. UI markdown renderer exists (`react-markdown`) but was **not** exercised with a real `succeeded` report this session. Chat **does** render the failure envelope. P2 “Send outreach” is a disabled placeholder. |

## Unit testing (`*test-unit`)

**Command**: `backend/.venv/bin/python -m pytest -v` (Python 3.13.9)  
**Result**: **15 passed**, 2 third-party deprecation warnings (FastAPI/httpx TestClient; crewai_tools lock_store import). No failures.

| Test | Maps to | Result |
|---|---|---|
| `test_exactly_three_agents_configured` | SAD §9 runtime guard / FR-2…FR-4 agent set | Pass |
| `test_exactly_three_tasks_configured` | SAD §9 runtime guard | Pass |
| `test_each_agent_has_role_goal_backstory` | Adapter mapping; `allow_delegation: false` | Pass |
| `test_each_task_has_expected_output_and_agent` | SAD §9 unit; FR-2…FR-4 output contracts | Pass |
| `test_final_task_has_two_item_context_chain` | SAD §2 context chaining (FR-4) | Pass |
| `test_no_linkedin_tool_referenced_anywhere` | PRD §3 MVP LinkedIn-drop / SAD §9 | Pass |
| `test_every_requisition_field_is_used_by_at_least_one_task` | FR-1 field completeness | Pass |
| `test_crew_module_has_no_linkedin_tool` | SAD §9 regression | Pass |
| `test_crew_module_uses_sequential_process` | Adapter: `Process.sequential`, `memory=False` | Pass |

**Frontend unit**: none exist (no test runner in `frontend/package.json`). Static checks this session:

- `npm run lint` (eslint) — 0 errors, 0 warnings
- `npx tsc --noEmit -p tsconfig.json` — clean

**Unit coverage gaps** (not failures of existing tests):

- `candidate_count` bounds (`ge=1, le=25`) are enforced by Pydantic and confirmed live (`422` for `0` and `26`) but have **no pytest**.
- Declared tools (`SerperDevTool`, `ScrapeWebsiteTool`) are not instantiated/bound in unit tests; only the LinkedIn-absence and YAML shape are guarded.
- Adapter baselines `max_iter=12`, `max_retry_limit=2`, `max_rpm=20` are in `crew.py` but not asserted by tests.
- No Prompt Trace capture to validate (known backend gap).

## Integration testing (`*test-integration`)

**Command**: same pytest run; `backend/tests/test_api.py` stubs `run_crew` per SAD §9 (avoid real LLM/search cost and nondeterminism).

| Test | Maps to | Result |
|---|---|---|
| `test_health_check` | SAD §5 `GET /health` | Pass |
| `test_submit_run_missing_required_fields_returns_422` | FR-1 / SAD §4 validation | Pass |
| `test_submit_run_returns_pending_run_id` | FR-1 async job pattern | Pass |
| `test_get_unknown_run_returns_404` | API contract | Pass |
| `test_full_run_lifecycle_succeeds` | FR-1 + FR-4 headings on stubbed report; `pending → succeeded` | Pass |
| `test_full_run_lifecycle_reports_failure` | PRD §6 error surfacing; `{code: pipeline_error}` | Pass |

**Cross-boundary gap vs SAD §9**: integration tests stub **`run_crew` as a whole**. They do **not** run the CrewAI crew with mocked LLM / Serper / scrape tool responses, so they cannot assert FR-2/FR-3 structured outputs or that the recommender actually emits both report sections from prior-task context. The success-path heading check is a string on the stub return value.

**FE↔API automated wiring tests**: none in-repo. This session’s browser checks (below) are manual/throwaway Playwright, matching the gap already recorded in `integration.md`.

## Smoke / acceptance (`*qa`) and flow verification (`*verify-flow`)

Live processes this session (then stopped): FastAPI `uvicorn app.main:app` on `127.0.0.1:8000`; Next.js `next dev` on `127.0.0.1:3000`. Browser checks used a throwaway Playwright/Chromium install under `/tmp` (not added to the repo).

### API smoke

| ID | Check | Result |
|---|---|---|
| SM-1 | `GET /health` → `200 {"status":"ok"}` | Pass |
| SM-2 | `POST /api/runs` missing `description` → `422` with FastAPI `detail` | Pass |
| SM-3 | empty `title` → `422` | Pass |
| SM-4 / SM-5 | `candidate_count` `0` and `26` → `422` | Pass |
| SM-6 | unknown `run_id` → `404` | Pass |
| SM-7 | CORS preflight `OPTIONS /api/runs` from `Origin: http://localhost:3000` → `200`, `access-control-allow-origin: *` | Pass |
| SM-8 | Valid submit → `202` `{status: pending}` → poll `running` → terminal `failed` with `error.code = pipeline_error` | Pass (failure path) |
| SM-9 | Trace Log JSONL written: `run_submitted` → `run_started` → `run_failed` | Pass (lifecycle only; no Prompt Trace) |

Live failure message this session: `Failed to connect to OpenAI API: Connection error.` The uvicorn process **did not** have `OPENAI_API_KEY` / `SERPER_API_KEY` / `CREWAI_TELEMETRY_OPT_OUT` in its environment (repo-root `.env` is not loaded by the app; see Defects). Crew console confirmed `research_candidates_task` started and interpolated title, description, responsibilities, requirements, preferred qualifications, perks, and `candidate_count=10` before the LLM error.

SAD §9 “one real (non-mocked) end-to-end run” **success** path (`pending → running → succeeded` + real report) is **not met**. Root `.env` still holds a placeholder `OPENAI_API_KEY`; `SERPER_API_KEY` is unset.

### UI / chat smoke (`*verify-flow`)

| ID | Check | Result |
|---|---|---|
| UI-1 | Heading “Recruitment Assistant” | Pass |
| UI-2 | Empty-state hint | Pass |
| UI-3 | “Start run” disabled without title + description | Pass |
| UI-4 | P2 panel (“Coming later”: run history, LinkedIn sourcing, send outreach, batch runs) visible, `aria-disabled` | Pass |
| UI-5 | Optional fields expand | Pass |
| UI-6 | “Start run” enables after required fields | Pass |
| UI-7 | Submit shows user bubble + loading (“Queuing run…” / “Researching, scoring, and drafting outreach…”) | Pass |
| UI-8 | Form shows “Run in progress…” while polling | Pass |
| UI-9 | Failure renders in chat: `Run failed (pipeline_error)` + backend message (PRD §6 — not silent) | Pass |
| UI-10 | After failure, button returns to “Start run”; form was auto-cleared so the button stays disabled until fields are filled again | Pass (see Known limitations) |
| UI-11 | Zero `pageerror` / console errors during the flow | Pass |
| UI-12 / UI-13 | Second run appends another user + error bubble (in-session chat history) | Pass |
| UI-14 | Backend stopped → `Run failed (network_error)` / `Failed to fetch` | Pass |

SSR `GET /` → `200` with job-title placeholder, “Start run”, and “Coming later” in the HTML.

**Not verified live**: `succeeded` assistant bubble rendering a real `## Recommendations` / `## Outreach Guidance` report. Rendering code is present (`ChatMessage` + `react-markdown` + GFM) and was previously exercised against a canned stub before integration replaced `runClient.ts`.

## Defects (`*log-defects`)

Severity is QA-local (not a security rating).

| ID | Severity | Summary | Evidence / impact |
|---|---|---|---|
| **DEF-1** | Medium | **Repo-root `.env` is not loaded by the FastAPI app.** `python-dotenv` is in `backend/requirements.txt` but `load_dotenv` is never called. Starting `uvicorn` from `backend/` leaves `OPENAI_API_KEY` unset even when `.env` exists at the repo root. | `ps` on the smoke uvicorn: no `OPENAI_API_KEY` in the process env. Live error was a generic OpenAI **connection** error rather than an auth `401`. Operator DX: easy to think keys “are in `.env`” while the pipeline never sees them. |
| **DEF-2** | Medium | **Live success-path smoke cannot pass in this environment.** Placeholder `OPENAI_API_KEY`; `SERPER_API_KEY` absent from `.env`. | Blocks SAD §9 real E2E success and FR-2…FR-4 content acceptance. Same gap as `backend.md` / `integration.md`. |
| **DEF-3** | Low | **No in-repo FE↔API regression test.** Chat wiring was verified with throwaway Playwright only. | A future `runClient.ts` / poll-loop change can break FR-1 without CI noticing. |
| **DEF-4** | Low | **CrewAI telemetry still attempted** during the live run (`telemetry.crewai.com` SSL failures in uvicorn logs) despite `.env.example` listing `CREWAI_TELEMETRY_OPT_OUT=true`. | Contributes log noise; related to DEF-1 (opt-out env not loaded). Not a functional FR failure. |
| **DEF-5** | Info / coverage | Integration tests do not execute the crew with mocked tools (SAD §9 wording). | FR-2/FR-3 outputs are untested except via YAML `expected_output` text. |

No functional UI crash, CORS block, or silent-failure defect was found on the implemented failure paths.

## Known limitations (implemented MVP, not defects)

- In-memory run store: state lost on process restart (PRD/SAD).
- No AuthN/AuthZ; CORS `allow_origins=["*"]` (SAD §8 MVP).
- Non-streaming; no per-agent-stage status in the API or UI (SAD §1 / frontend.md).
- Polling loop has **no timeout or cancel** (`page.tsx` `POLL_INTERVAL_MS = 700` until `succeeded`/`failed`).
- Requisition form **clears on submit**, so a failed run requires re-typing. Optional fields also collapse.
- User chat bubble shows **title + description only** (not responsibilities/requirements/perks/`candidate_count`).
- No Prompt Trace (adapter logging requirement; recorded in `backend.md`).
- `FutureFeaturesPanel` is static copy of PRD §4 P2, not wired to flags.

## Future work (`*future-work`)

**Testing (non-MVP / next QA pass)** — do not treat as current-build failures:

- One live success-path run with real `OPENAI_API_KEY` and `SERPER_API_KEY` (operator-supplied); confirm `succeeded` + two-section report in chat.
- Commit a Playwright (or similar) smoke against FE+API if repeatable browser coverage is wanted (called out in `integration.md`; not added this session).
- Crew-level integration with mocked LLM/search/scrape tools asserting FR-2 list bound, FR-3 scores, FR-4 headings from real task chaining.
- Frontend unit tests for `RequisitionForm` (required-field gating, `candidate_count` clamp) and `runClient` envelope mapping (`422` → `validation_error`, network → `network_error`).
- Pytest for `candidate_count` bounds and adapter numeric controls (`max_iter` / `max_rpm`).
- Prompt Trace capture + assertion once backend implements it.
- Cancel / max-wait UX for long runs (PRD has no SLA; still operator-useful).
- Performance / load / a11y audits — out of MVP scope (`aamad.config.yml` / this persona’s prohibited non-functional testing unless scoped).

**Product P2 (already in UI placeholders; PRD §4)** — not tested as features:

- Authenticated LinkedIn sourcing (explicitly excluded; regression-guarded).
- Actual outreach send.
- Persistent run history / candidate storage.
- Multi-requisition batch / multi-user.

## Runtime adapter checks (crewai)

| Adapter / SAD check | Result |
|---|---|
| `Process.sequential`, `memory=False`, 3 agents / 3 tasks | Pass (unit) |
| No LinkedIn tool bound | Pass (unit + source guard) |
| `Task.context` on recommender = both prior tasks | Pass (unit) |
| `max_iter <= 12`, `max_retry_limit >= 2`, crew `max_rpm` | Present in `crew.py`; not separately tested |
| Least-privilege tools = Serper + scrape only | Present in `crew.py._tools()`; not bind-tested |
| Trace Log under `project-context/2.build/logs` | Pass for lifecycle events; files gitignored |
| Prompt Trace | **Missing** (deferred) |
| Cancellation / timeout of a running crew | **Not implemented** (deferred) |

## Recommendation

1. **Next persona**: `@security.eng` (`*assess-security`) — required by `aamad.config.yml` `security.require_security_assessment: true` and SAD §8 before Deliver.
2. Do **not** treat SAD §9 live success-path smoke as closed until the operator supplies real API keys **and** the process actually loads them (DEF-1/DEF-2).
3. `@devops.eng` should document how to start uvicorn with the repo-root env file (or `@backend.eng` should call `load_dotenv` against a known path).

## Sources

- `project-context/1.define/prd.md` (FR-1…FR-4, §5–§6 error/UX, §9 QA intent)
- `project-context/1.define/sad.md` (§4 API, §6 flow, §9 Testing)
- `project-context/2.build/frontend.md`
- `project-context/2.build/backend.md`
- `project-context/2.build/integration.md`
- `aamad.config.yml` (testing + security gates)
- `.cursor/rules/adapter-crewai.mdc`
- `.cursor/agents/qa-eng.md`
- Live: `backend/tests/*` (15 passing), `backend/app/main.py` / `crew.py` / `config/*.yaml`, `frontend/src/app/page.tsx`, `frontend/src/lib/runClient.ts`, `frontend/src/components/*`

## Assumptions

- Missing `system-description.md` / user stories means PRD FR-1…FR-4 are the acceptance IDs (`AC-*` N/A).
- Missing `setup.md` does not block QA; runtime layout is as built under `backend/` and `frontend/`.
- SAD §9’s “mocked LLM and search/scrape tool responses” is only partially met by stubbing `run_crew`; recorded as DEF-5 rather than a failed existing test.
- Throwaway `/tmp` Playwright is verification-only, not a project deliverable (same stance as `integration.md`).
- A generic OpenAI “Connection error” with unset keys is an environment/config failure, not a chat-flow logic failure, provided the UI still shows `pipeline_error`.

## Open Questions

- Will the operator provide valid `OPENAI_API_KEY` and `SERPER_API_KEY` for a success-path re-run before Deliver?
- Should `@backend.eng` load repo-root `.env` in-app, or is `--env-file` / exported env the intended contract for `@devops.eng`?
- Is stubbing `run_crew` sufficient for CI, or should a mocked-crew integration test be required before calling FR-2…FR-4 “tested”?
- Confirm merged recommender output shape in a real report (carried from PRD/SAD) once a live success run exists.
- Frontend poll timeout / cancel: in or out of MVP UX?

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `qa-eng`
- **Actions**: `test-unit`, `test-integration`, `qa`, `verify-flow`, `log-defects`, `future-work`
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai` (from `aamad.config.yml` `runtime.target`; this session’s shell had `AAMAD_TARGET_RUNTIME` unset)
- **Upstream artifacts**: `prd.md`, `sad.md`, `frontend.md`, `backend.md`, `integration.md`, `aamad.config.yml`
- **Test results**: backend pytest **15/15 pass**; frontend eslint clean; `tsc --noEmit` clean; live API failure-path `pending → running → failed`; live UI chat failure-path + `network_error` path pass; live success-path **blocked** (DEF-1, DEF-2)
- **Prompt Trace**: omitted — this artifact records QA execution, not a production LLM task; no CrewAI Prompt Trace exists in the app to attach
- **Next**: `@security.eng` before Phase 3 Deliver
