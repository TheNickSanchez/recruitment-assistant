# System Architecture Document (SAD) — Recruitment Assistant

**Persona**: @system.arch | **Action**: `*create-sad` | **Status**: Draft v2

**Revision note (2026-08-20)**: this SAD supersedes Draft v1. Two changes were made at explicit user
direction: (1) the agent design changed from 4 agents (researcher, matcher, communicator, reporter) to 3
agents (**researcher, evaluator, recommender**), matching a corresponding revision to
`project-context/1.define/prd.md`; (2) the backend framework, previously left open for `@backend.eng` to
decide, is now fixed to **FastAPI** in this SAD.

## Input Requirements

**PRD Document**: `project-context/1.define/prd.md` (Draft v1, revised 2026-08-20 — 3-agent design)
**MRD**: `project-context/1.define/mrd.md`
**User Stories**: none exist yet (`*create-stories` was not run) — architecture below is derived directly
from PRD §3–§7; feature-level detail should be refined into SFS documents once stories exist.
**MVP Scope**: Core 3-agent pipeline behind a minimal chat interface (PRD §1, §3, §6).
**Selected Runtime**: `crewai` (resolved from `aamad.config.yml` → `runtime.target: crewai`; no
`AAMAD_TARGET_RUNTIME` env var override observed). **Confirmed for this revision.**

## 1. MVP Architecture Philosophy & Principles

**MVP Design Principles**:
- Single operator, single requisition per run — no multi-tenancy, no concurrency requirement (PRD §2, §3).
- Reproducibility over cleverness: sequential, stateless pipeline; no crew memory by default (PRD §3, §5;
  adapter rule "Memory" — default `memory=False`).
- Observable by default: basic run/console logging and a Prompt Trace are required by the adapter rule's
  "Logging" section, even though PRD does not mandate a dedicated observability stack.
- Deploy scaffolding is in scope for Phase 3 but is minimal (single-instance/local target — PRD §3
  Infrastructure Specifications).

**Core vs. Future Features** (traced to PRD §4):
- **MVP (Core)**: 3-agent sequential crew (research → evaluate/score → recommend with outreach
  guidance), chat interface for requisition submission and report display, env-var-only secrets.
- **Future (explicit deferrals, PRD §4 P2)**: authenticated LinkedIn sourcing, actual outreach *sending*,
  persistent storage across runs, multi-requisition/multi-user support. None of these are designed for in
  this SAD.

**Technical Architecture Decisions**:
- **Frontend framework**: not mandated by PRD or MRD (PRD §6 specifies "minimal chat interface," not a
  library). No single vendor UI library is hardcoded here — `@frontend.eng` selects a lightweight web chat
  framework at Build time. Recorded as an Assumption below, not a PRD requirement.
- **Backend framework — FastAPI (fixed in this revision)**: Python-native, async-first, and directly fits
  the async submit/poll job pattern this SAD already requires (§4) to wrap a multi-minute CrewAI run
  without blocking. Flask was the other option under consideration; FastAPI is preferred because its
  native `async def` endpoints and background-task support avoid extra threading/worker-pool wiring that
  Flask's WSGI model would otherwise need for the same non-blocking behavior. This is an architecture
  decision, not a PRD requirement — PRD §3 leaves the framework unspecified.
- **UI approach**: single-turn-per-run interaction — operator submits one requisition, waits, receives one
  report (PRD §6: "Operator interacts once per run"). No multi-turn conversational back-and-forth is
  required for MVP.
- **Agent communication pattern**: CrewAI sequential process, task-context chaining (no delegation) —
  directly matches PRD §3's Core Agent Definitions and the adapter rule's "Execution" guidance to prefer
  sequential mode for reproducible MVP builds.
- **Streaming vs. non-streaming**: **non-streaming** for MVP, unchanged from Draft v1. Streaming
  intermediate agent output is not required by any PRD acceptance criterion.

## 2. Multi-Agent System Specification

**Agent Architecture** (3 agents — within the template's 3–4 max; traced to PRD §3 Core Agent
Definitions, revised 2026-08-20):

| Agent | Role | Goal | Tools (MVP) | Delegation | Memory |
|---|---|---|---|---|---|
| `researcher` | Job Candidate Researcher | Find potential candidates for the job | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |
| `evaluator` | Candidate Evaluator and Scorer | Evaluate and score candidates against the job requirements | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |
| `recommender` | Candidate Recommendation and Outreach Strategist | Recommend the best candidates, with outreach guidance | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |

- **No LinkedIn tool**: unchanged from Draft v1 — confirms PRD §3's explicit MVP decision to exclude the
  reference example's LinkedIn-cookie-scraping tool. Not present in any agent's tool list above.
- **`recommender` carries tools where the reference `reporter` had none**: because `recommender` absorbs
  both the former `communicator` role (which needed web tools to research outreach channels/templates)
  and the former `reporter` role (which needed none, only synthesis), the merged agent keeps the tool set
  of the more capability-requiring predecessor (PRD §3 revision note).
- **Memory / session**: `memory=False` at the crew level, per adapter rule default and PRD's stateless-run
  design (PRD §3, §5). Each run is independent; nothing carries over between requisitions.
- **Tool/MCP integration**: least-privilege — all three agents get the same web search/scrape tool pair;
  no agent has a broader tool set than needed for its stage.

**Task / Turn Orchestration**:
- **Dependencies**: `research_candidates_task` → `evaluate_and_score_candidates_task` →
  `recommend_candidates_task`, where the final task's `Task.context` includes the outputs of both prior
  tasks (PRD §3, revised).
- **Expected outputs / data formats**:
  - `research_candidates_task` → bounded candidate list (default 10) with contact info + brief profile
    (PRD FR-2). Unchanged.
  - `evaluate_and_score_candidates_task` → ranked, scored, justified candidate list (PRD FR-3, renamed
    from "match & score"); must not attempt direct LinkedIn scraping (constraint carried from
    PRD/reference task description).
  - `recommend_candidates_task` → single consolidated markdown report containing **both** candidate
    recommendations with scores/justifications **and** outreach methods/message templates per
    candidate/segment, draft-only (PRD FR-4, merged from the former FR-4/FR-5).
- **Context passing**: CrewAI `Task.context=[...]` list, not shared crew memory — deterministic,
  explicit dependency flow per adapter rule "Mapping." Now a 2-item context list on the final task
  (previously 3, since there are only 2 prior tasks instead of 3).
- **Error handling / retries / cancellation**: unchanged from Draft v1 — `max_retry_limit >= 2` per task;
  halt and write a Diagnostic on missing prerequisites, unresolved tools, or guardrail failure (adapter
  rule "Failure Policy").
- **Performance budgets**: `max_iter <= 12` per task (adapter rule baseline); `max_rpm` set at crew level.
  With one fewer agent/task than Draft v1, expected end-to-end LLM/tool-call volume per run is lower,
  modestly reducing the cost-exposure risk noted in the MRD Risk Matrix.

**Runtime-Conditional Configuration — `crewai`**:
- **Crew composition**: 3 agents as specified above, defined via `@CrewBase`-style class.
- **Process type**: `Process.sequential` (unchanged — no hierarchical/manager-agent pattern).
- **YAML agent/task config**: externalized to `config/agents.yaml` and `config/tasks.yaml` under the
  backend runtime package, per adapter rule "Setup"/"Mapping" — hard requirement of the adapter.
- **`max_iter`**: ≤ 12 per task (baseline; unchanged).
- **Task context chaining**: `recommend_candidates_task.context` includes the two prior tasks' outputs
  (reduced from 3 to 2 given the merged final agent).

## 3. Frontend Architecture Specification

**Technology Stack**: Not fixed by PRD — deferred to `@frontend.eng` (see §1 Technical Architecture
Decisions). Minimum requirement: a single web page capable of (a) a form/text-area for job-requisition
input and (b) rendering a returned markdown report. No specific framework, styling system, or state
manager is mandated here. Unchanged from Draft v1.

**Application Structure**:
- Single route/page for MVP (submit requisition → view report).
- API client boundary: the frontend calls the FastAPI backend's run-submission/status API (see §4) and
  does not talk to the CrewAI runtime, LLM, or search provider directly.
- Responsive/accessibility requirements: none mandated by PRD.

**Interface Requirements**:
- Primary surface: a chat-style input for the job requisition and a chat-style (or simple panel) display
  for the final report, per PRD §6.
- Loading state: required — a run takes on the order of minutes (PRD §5).
- Error state: required — PRD §6 states errors "should surface to the operator in the chat rather than
  fail silently."
- Placeholders for Future Work are optional for MVP; not required by PRD.

## 4. Backend Architecture Specification

**Framework — FastAPI (fixed in this revision)**:
- Chosen over Flask for native async support, which pairs directly with the async job-submission pattern
  this SAD requires below, and for built-in request/response schema validation (via Pydantic), which
  simplifies the run-submission validation requirement in PRD §3/§4 without extra libraries.
- Implication for Build: `@backend.eng` scaffolds a FastAPI app (e.g., `app/main.py` + routers), not a
  Flask app. This is now a fixed architecture decision, not an open choice.

**API Architecture**:
- **Run submission endpoint**: `POST /api/runs` — accepts a job requisition (title, description,
  responsibilities, requirements, preferred qualifications, perks — matching the reference `main.py`
  input shape and PRD FR-1) and returns a `run_id`. Implemented as a FastAPI async endpoint that schedules
  the crew run as a background task (e.g., via FastAPI `BackgroundTasks` or an equivalent async task
  runner) rather than awaiting the full multi-minute pipeline inline.
- **Run status/result endpoint**: `GET /api/runs/{run_id}` — returns run status (`pending` |
  `running` | `succeeded` | `failed`) and, once `succeeded`, the consolidated markdown report (PRD FR-4).
- **Architecture decision — async job pattern over a single blocking call**: unchanged rationale from
  Draft v1 — a full crew run can take minutes (PRD §5), so a submit-then-poll pattern avoids
  client/proxy-timeout failure modes not required by any PRD acceptance criterion. Still recorded as an
  Open Question for `@backend.eng`/`@integration.eng` to confirm a simpler synchronous call isn't
  preferred for a purely local/personal deployment.
- **Validation**: FastAPI/Pydantic request models reject a run submission missing required requisition
  fields (title + description, at minimum) with FastAPI's structured `422` validation-error response; no
  rate limiting required at MVP (single operator).
- **Error envelope**: FastAPI's default validation-error shape for input errors; a custom
  `{ "error": { "code": string, "message": string } }` envelope for run-failure states (e.g., a
  `failed`-status run), sufficient for the frontend's required error-surfacing behavior (PRD §6).

**Data Architecture**:
- **None for MVP** — unchanged from Draft v1; explicitly deferred per PRD §3/§4. Run state
  (`pending`/`running`/`succeeded`/`failed` + result) may live in-process/in-memory only for the duration
  of a run.

**Runtime Integration Layer**:
- The FastAPI layer invokes the CrewAI crew (`crew.kickoff(inputs={...})`) using the job requisition as
  `inputs`, adapted to the 3-agent/no-LinkedIn tool set in §2.
- Agent/task configuration lives in `config/agents.yaml` / `config/tasks.yaml` (adapter rule "Setup"); the
  API layer does not hardcode agent definitions.
- **Prompt Trace and Trace Log**: captured per adapter rule "Logging" — persisted under
  `project-context/2.build/logs`, secrets redacted. Unchanged from Draft v1.

**Authentication & Secrets**:
- No end-user authentication on the API for MVP — single local/personal operator (PRD §3). Unchanged.
- Secrets referenced by name only, via environment variables. Expected `.env.example` entries (names
  only):
  - `LLM_API_KEY` / `OPENAI_API_KEY` (provider TBD — PRD Open Question; note `.env.example` currently
    references `OPENAI_API_KEY`/`OPENAI_MODEL`, which is a signal toward OpenAI but not yet a confirmed
    user decision)
  - `SERPER_API_KEY` (matching the reference implementation's `SerperDevTool` provider; PRD Open Question
    on whether to confirm this provider)

## 5. DevOps & Deployment Architecture

Unchanged from Draft v1.

**CI/CD (minimal MVP)**: lint + unit tests + build only.

**Hosting**: smallest MVP-appropriate target — a single-instance local or lightly-hosted Python (FastAPI,
via e.g. `uvicorn`) process. A `GET /health` endpoint should exist for operational sanity.

**IaC / multi-region / advanced monitoring**: explicitly Future Work.

**Observability**: baseline logs and the Prompt Trace/Trace Log described in §4.

## 6. Data Flow & Integration Architecture

1. Operator enters a job requisition in the chat UI → `POST /api/runs`.
2. FastAPI backend validates input (Pydantic model), creates a `run_id`, and schedules the CrewAI crew
   run as a background task with the requisition as `inputs`.
3. `researcher` agent calls `SerperDevTool`/`ScrapeWebsiteTool` to source candidates → output passed via
   `Task.context` to `evaluator`.
4. `evaluator` scores/ranks candidates (same tool set, no LinkedIn scraping) → output passed to
   `recommender`.
5. `recommender` synthesizes both prior outputs into one markdown report containing candidate
   recommendations **and** outreach guidance/templates (draft-only, no send action); run status flips to
   `succeeded` with the report attached.
6. Chat UI polls/fetches `GET /api/runs/{run_id}` and renders the report; on any stage failure, status
   flips to `failed` with an error message surfaced in the chat (PRD §6).

**External integrations required for MVP only**: one LLM API, one web-search/scrape API (Serper by
default, per reference). No other third-party integration is in scope.

## 7. Performance & Scalability Specifications

- **Response-time target**: no hard SLA (PRD §5); a run is expected to take "on the order of minutes,"
  likely somewhat less than the Draft v1 estimate given one fewer sequential agent stage.
- **Concurrency**: single operator, effectively one run at a time for MVP.
- **Scaling path**: explicitly deferred.
- **Token/cost controls**: `max_rpm` at the crew level and the bounded candidate-list default (~10)
  remain the primary cost controls; the 3-agent design further reduces per-run LLM call volume relative
  to Draft v1's 4-agent design.

## 8. Security & Compliance Architecture

Unchanged from Draft v1.

- **AuthN/AuthZ**: none for MVP. Flagged as an Open Question if ever exposed beyond localhost.
- **Secrets**: environment variables only.
- **Input validation baseline**: FastAPI/Pydantic required-field validation on run submission (§4).
- **Third-party data exposure**: unresolved Open Question, carried from PRD.
- **Compliance**: no regulatory review performed — explicitly deferred.
- **Security assessment**: required before Deliver per `aamad.config.yml`
  (`security.require_security_assessment: true`) — `@security.eng` must review before Phase 3.

## 9. Testing & Quality Assurance Specifications

- **Unit tests**: agent/task YAML config loads without error; each declared tool is bindable; task
  `expected_output` fields are present; FastAPI request validation (missing required fields returns
  `422`) — mapped to PRD FR-1.
- **Integration tests**: full crew run end-to-end against FR-1…FR-4, using mocked/stubbed LLM and
  search/scrape tool responses to avoid real API cost and nondeterminism in CI; assert the final report
  contains sections corresponding to candidate recommendations and outreach guidance (PRD FR-4).
- **Smoke/acceptance**: one real (non-mocked) end-to-end run against a sample job requisition, verifying
  the async job pattern (`pending` → `running` → `succeeded`) via the FastAPI endpoints, and that the
  chat UI can submit a requisition and render the resulting report (PRD §6).
- **Runtime-specific checks**: validate Prompt Trace/Trace Log entries per task; validate no
  `LinkedInTool` (or equivalent) is bound to any agent, as a regression guard on the explicit MVP scope
  decision in PRD §3; validate exactly 3 agents / 3 tasks are configured (regression guard on this
  revision's agent-count change).
- **Security assessment**: recommended/required before Deliver, per §8 above.

## 10. MVP Launch & Feedback Strategy

Unchanged from Draft v1.

- **Beta/pilot criteria**: N/A — single operator is both builder and user.
- **Success metrics tied to PRD KPIs** (PRD §7): recruiter time saved (hours/week, no sourced baseline
  yet); run completes end-to-end without manual intervention; candidate list stays within bounded
  default; operator finds each report actionable.
- **Iteration priorities after first real run**: revisit the async-job-vs-synchronous decision (§4) and
  the LLM/search-provider Open Questions based on actual run-time and cost observed; confirm whether the
  merged `recommender` output (recommendations + outreach guidance in one report) reads well as a single
  document or should be split back into two sections/agents.

## Implementation Guidance for AI Development Agents

1. **Foundation setup** (`@project.mgr`, `*setup-project`): scaffold repo structure, Python environment,
   FastAPI dependency, `.env.example` with `LLM_API_KEY`/`OPENAI_API_KEY` / `SERPER_API_KEY` placeholder
   names (no values), per §4.
2. **Frontend MVP UI** (`@frontend.eng`, `*develop-fe`): build the single-page chat UI per §3, without
   backend wiring.
3. **Backend runtime scaffolding** (`@backend.eng`, `*develop-be`): implement `config/agents.yaml`,
   `config/tasks.yaml` (3 agents/tasks per §2), crew entrypoint, and the FastAPI `POST /api/runs` /
   `GET /api/runs/{run_id}` endpoints per §4.
4. **Integration** (`@integration.eng`, `*integrate-api`): wire the chat UI to the run-submission/status
   API; verify the async status-polling round trip.
5. **QA** (`@qa.eng`): unit + integration + smoke tests per §9, mapped to PRD FR-1…FR-4.
6. **Security** (`@security.eng`): assessment per §8 before Deliver.
7. **Deliver** (`@devops.eng`): minimal deploy/CI/runbook per §5.

## Architecture Validation Checklist

- [x] PRD requirements mapped to architectural components (FR-1…FR-4 traced throughout §2–§6)
- [x] Agents designed for the domain and selected runtime (3-agent CrewAI sequential crew, §2)
- [x] Frontend and backend contracts agree on schemas — async job submit/poll contract defined in §4
  (FastAPI/Pydantic)
- [x] Secrets via env vars only (§4, §8)
- [x] MVP vs. Future Work boundaries explicit (§1, throughout)
- [x] Resolved `AAMAD_TARGET_RUNTIME` recorded in Audit

## Sources

- `project-context/1.define/prd.md` (Draft v1, revised 2026-08-20 — §3–§7, agent redesign and revision
  note)
- `project-context/1.define/mrd.md` (§2 Technical Feasibility, Risk Assessment Matrix)
- `.cursor/rules/adapter-crewai.mdc` (runtime-specific setup, execution, tools, logging, quality gates,
  failure policy, memory rules)
- `.cursor/rules/aamad-core.mdc` (cross-persona contracts)
- `aamad.config.yml` (resolved `runtime.target: crewai`; security/testing/documentation gates)
- `.cursor/templates/sad-template.md` (this document's own template/instructions)
- User instruction (this session, 2026-08-20): directed the 3-agent redesign (Researcher, Evaluator,
  Recommender) and the FastAPI backend choice.

## Assumptions

- Frontend framework/library is unspecified by PRD and left to `@frontend.eng`'s discretion at Build time.
- An async submit-then-poll API pattern (§4) is adopted as the MVP default over a single blocking call.
- Run state may be held in-process/in-memory only (no database).
- `max_iter <= 12`, `max_retry_limit >= 2`, and crew-level `max_rpm` are adopted from the adapter rule's
  baseline controls.
- **FastAPI's built-in `BackgroundTasks`** (or an equivalent async task mechanism) is assumed sufficient
  for the async job pattern at MVP scale (single operator, one run at a time); a dedicated task
  queue/worker (e.g. Celery, RQ) is not assumed necessary and would be over-engineering for this scope.
- The merged `recommender` agent's report is assumed to present recommendations and outreach guidance as
  two sections within one document, preserving both prior agents' output content rather than dropping
  either — this is an inference from the user's instruction to merge agents, not an explicit output-format
  directive from the user (carried from the PRD's corresponding Assumption).

## Open Questions

- **LLM provider/model** (carried from PRD): still unresolved; `.env.example` hints at OpenAI but this
  isn't confirmed. This SAD's runtime-integration layer (§4) is provider-agnostic by design.
- **Web-search provider** (carried from PRD): assumed to be Serper but not confirmed.
- **Synchronous vs. async API pattern**: confirm whether a simpler synchronous FastAPI endpoint is
  acceptable instead of the async submit/poll pattern for a purely local, single-operator deployment.
- **Deployment exposure**: if ever exposed beyond localhost, the "no AuthN/AuthZ for MVP" decision in §8
  needs revisiting.
- **Third-party data-handling review** (carried from PRD): not resolved here.
- **Time-savings baseline** (carried from PRD §7): still not logged.
- **Merged `recommender` output shape** (carried from PRD): confirm whether recommendations and outreach
  guidance should stay as two sections in one report, as assumed above.

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `system-arch`
- **Action**: `create-sad`
- **Resolved AAMAD_TARGET_RUNTIME**: AAMAD_TARGET_RUNTIME=crewai (from `aamad.config.yml`; no environment variable override observed)
- **Upstream artifacts**: `project-context/1.define/prd.md` (revised 2026-08-20),
  `project-context/1.define/mrd.md`
- **Revision**: 2026-08-20 — superseded Draft v1. Changed agent design from 4 agents
  (researcher/matcher/communicator/reporter) to 3 agents (researcher/evaluator/recommender) at explicit
  user direction, matching a corresponding PRD revision. Fixed the backend framework to FastAPI (was
  previously deferred to Build time), also at explicit user direction, with rationale recorded in §1/§4.
