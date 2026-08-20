# System Architecture Document (SAD) — Recruitment Assistant

**Persona**: @system.arch | **Action**: `*create-sad` | **Status**: Draft v1

## Input Requirements

**PRD Document**: `project-context/1.define/prd.md`
**MRD**: `project-context/1.define/mrd.md`
**User Stories**: none exist yet (`*create-stories` was not run) — architecture below is derived directly
from PRD §3–§7; feature-level detail should be refined into SFS documents once stories exist.
**MVP Scope**: Core 4-agent pipeline behind a minimal chat interface (PRD §1, §3, §6).
**Selected Runtime**: `crewai` (resolved from `aamad.config.yml` → `runtime.target: crewai`; no
`AAMAD_TARGET_RUNTIME` env var override observed).

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
- **MVP (Core)**: 4-agent sequential crew (research → match/score → outreach draft → report), chat
  interface for requisition submission and report display, env-var-only secrets.
- **Future (explicit deferrals, PRD §4 P2)**: authenticated LinkedIn sourcing, actual outreach *sending*,
  persistent storage across runs, multi-requisition/multi-user support. None of these are designed for in
  this SAD.

**Technical Architecture Decisions**:
- **Frontend framework**: not mandated by PRD or MRD (PRD §6 specifies "minimal chat interface," not a
  library). Per template guidance, no single vendor UI library is hardcoded here — `@frontend.eng` selects
  a lightweight web chat framework (e.g., a small React/Vite single-page app, or an even simpler
  server-rendered chat page) at Build time. **Decision recorded as an Assumption below**, not a PRD
  requirement.
- **UI approach**: single-turn-per-run interaction — operator submits one requisition, waits, receives one
  report (PRD §6: "Operator interacts once per run"). No multi-turn conversational back-and-forth is
  required for MVP.
- **Agent communication pattern**: CrewAI sequential process, task-context chaining (no delegation) —
  directly matches PRD §3's Core Agent Definitions and the adapter rule's "Execution" guidance to prefer
  sequential mode for reproducible MVP builds.
- **Streaming vs. non-streaming**: **non-streaming** for MVP. A full crew run involves 4 sequential
  LLM-driven stages with tool calls (PRD §5: "on the order of minutes," no hard SLA) — streaming
  intermediate agent output is not required by any PRD acceptance criterion, so it is deferred to reduce
  Build complexity. See §3 below for the resulting async-job API pattern this implies.

## 2. Multi-Agent System Specification

**Agent Architecture** (4 agents — within the template's 3–4 max; traced to PRD §3 Core Agent Definitions):

| Agent | Role | Goal | Tools (MVP) | Delegation | Memory |
|---|---|---|---|---|---|
| `researcher` | Job Candidate Researcher | Find potential candidates for the job | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |
| `matcher` | Candidate Matcher and Scorer | Match candidates to the job and score them | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |
| `communicator` | Candidate Outreach Strategist | Develop outreach strategies for selected candidates | `SerperDevTool`, `ScrapeWebsiteTool` | `allow_delegation=False` | none |
| `reporter` | Candidate Reporting Specialist | Report the best candidates to the recruiter | none | `allow_delegation=False` | none |

- **No LinkedIn tool**: confirms PRD §3's explicit MVP decision to exclude the reference example's
  LinkedIn-cookie-scraping tool. Not present in any agent's tool list above.
- **Memory / session**: `memory=False` at the crew level, per adapter rule default and PRD's stateless-run
  design (PRD §3, §5). Each run is independent; nothing carries over between requisitions.
- **Tool/MCP integration**: least-privilege — only `researcher`, `matcher`, and `communicator` get web
  search/scrape tools (matching PRD's per-agent tool lists exactly); `reporter` gets none, since its job is
  to synthesize prior task outputs, not to search further.

**Task / Turn Orchestration**:
- **Dependencies**: `research_candidates_task` → `match_and_score_candidates_task` →
  `outreach_strategy_task` → `report_candidates_task`, where the final task's `Task.context` includes the
  outputs of all three prior tasks (PRD §3; matches the verified reference `crew.py` pattern cited in the
  MRD).
- **Expected outputs / data formats**:
  - `research_candidates_task` → bounded candidate list (default 10) with contact info + brief profile
    (PRD FR-2).
  - `match_and_score_candidates_task` → ranked, scored, justified candidate list (PRD FR-3); must not
    attempt direct LinkedIn scraping (constraint carried from PRD/reference task description).
  - `outreach_strategy_task` → outreach methods + message templates, draft-only (PRD FR-4).
  - `report_candidates_task` → single consolidated markdown report (PRD FR-5).
- **Context passing**: CrewAI `Task.context=[...]` list, not shared crew memory — deterministic,
  explicit dependency flow per adapter rule "Mapping."
- **Error handling / retries / cancellation**: per adapter rule "Execution" baseline controls —
  `max_retry_limit >= 2` per task; on missing runtime prerequisites, unresolved tools, or guardrail failure,
  halt and write a Diagnostic rather than partially complete a report (adapter rule "Failure Policy"). No
  PRD requirement for retry/resume beyond this baseline (PRD §5 explicitly defers fault tolerance).
- **Performance budgets**: `max_iter <= 12` per task (adapter rule baseline, no PRD override); `max_rpm` set
  at crew level for budget stability, directly mitigating the MRD's "Medium Risk: unbounded cost exposure"
  and PRD §7's technical metric to keep candidate-list size bounded (~10).

**Runtime-Conditional Configuration — `crewai`**:
- **Crew composition**: 4 agents as specified above, defined via `@CrewBase`-style class (matching the
  reference implementation's structure).
- **Process type**: `Process.sequential` (no hierarchical/manager-agent pattern; PRD and reference both use
  sequential only — hierarchical mode would require its own SAD justification per adapter rule, which is
  not given here).
- **YAML agent/task config**: externalized to `config/agents.yaml` and `config/tasks.yaml` under the
  backend runtime package, per adapter rule "Setup"/"Mapping" — this is a hard requirement of the adapter,
  not optional.
- **`max_iter`**: ≤ 12 per task (baseline; no task in this pipeline is expected to need more given bounded
  candidate-list scope).
- **Task context chaining**: as described above; `report_candidates_task.context` includes the three prior
  tasks' outputs.

## 3. Frontend Architecture Specification

**Technology Stack**: Not fixed by PRD — deferred to `@frontend.eng` (see §1 Technical Architecture
Decisions). Minimum requirement: a single web page capable of (a) a form/text-area for job-requisition
input and (b) rendering a returned markdown report. No specific framework, styling system, or state
manager is mandated here.

**Application Structure**:
- Single route/page for MVP (submit requisition → view report). No routing complexity needed given the
  single-turn-per-run interaction model (§1).
- API client boundary: the frontend calls the backend's chat/run API (see §4) and does not talk to the
  CrewAI runtime, LLM, or search provider directly — those integrations are backend-only (adapter rule
  "Tools": bind tools only within the runtime layer).
- Responsive/accessibility requirements: none mandated by PRD (PRD §6: "not a formal requirement for
  MVP"); default to whatever the chosen minimal framework provides out of the box.

**Interface Requirements**:
- Primary surface: a chat-style input for the job requisition and a chat-style (or simple panel) display
  for the final report, per PRD §6.
- Loading state: required — a run takes on the order of minutes (PRD §5), so the UI must show that a run
  is in progress rather than appearing frozen.
- Error state: required — PRD §6 states errors "should surface to the operator in the chat rather than
  fail silently." Exact error-message format is left to `@integration.eng` (PRD §6), not fixed here.
- Placeholders for Future Work (LinkedIn sourcing, outreach sending, persistence, multi-user) are optional
  for MVP; not required by PRD.

## 4. Backend Architecture Specification

**API Architecture**:
- **Run submission endpoint**: `POST /api/runs` — accepts a job requisition (title, description,
  responsibilities, requirements, preferred qualifications, perks — matching the reference `main.py`
  input shape and PRD FR-1) and returns a `run_id`.
- **Run status/result endpoint**: `GET /api/runs/{run_id}` — returns run status (`pending` |
  `running` | `succeeded` | `failed`) and, once `succeeded`, the consolidated markdown report (PRD FR-5).
- **Architecture decision — async job pattern over a single blocking call**: because a full crew run can
  take minutes (PRD §5) and involves multiple sequential LLM + tool calls, a single synchronous HTTP
  request risks client/proxy timeouts. An async submit-then-poll pattern is therefore the MVP default,
  even though PRD does not explicitly require it — this is an architecture decision made to satisfy PRD's
  implicit reliability expectation (errors surface to the operator, PRD §6) without inventing new product
  scope. A simpler synchronous call is an acceptable Build-time simplification for a purely local/personal
  deployment; recorded as an Open Question below for `@backend.eng`/`@integration.eng` to confirm.
- **Validation**: reject a run submission missing required requisition fields (title + description, at
  minimum) with a structured error envelope; no rate limiting required at MVP (single operator).
- **Error envelope**: `{ "error": { "code": string, "message": string } }` — minimal shape sufficient for
  the frontend's required error-surfacing behavior (PRD §6).

**Data Architecture**:
- **None for MVP** — explicitly deferred per PRD §3/§4 (stateless runs, no persistent storage). Run
  state (`pending`/`running`/`succeeded`/`failed` + result) may live in-process/in-memory only for the
  duration of a run; it does not need to survive a process restart for MVP. If an operator needs a report
  after closing the browser tab, that is out of scope until Future Work "persistent candidate/report
  storage" (PRD §4 P2) is picked up.

**Runtime Integration Layer**:
- The API layer invokes the CrewAI crew (`crew.kickoff(inputs={...})`) using the job requisition as
  `inputs`, matching the reference `main.py` pattern, adapted to the 4-agent/no-LinkedIn tool set in §2.
- Agent/task configuration lives in `config/agents.yaml` / `config/tasks.yaml` (adapter rule "Setup"); the
  API layer does not hardcode agent definitions.
- **Prompt Trace and Trace Log**: captured per adapter rule "Logging" — rendered prompts before execution,
  and lifecycle events (task start/stop, retries, guardrail outcomes) — persisted under
  `project-context/2.build/logs`, not inline in generated code, and with secrets redacted.

**Authentication & Secrets**:
- No end-user authentication on the API for MVP — single local/personal operator (PRD §3: "no end-user
  authentication requirement... single local operator").
- Secrets referenced by name only, via environment variables — no values in any artifact
  (`aamad.config.yml`: `security.forbid_committed_secrets: true`; adapter rule "Setup"). Expected
  `.env.example` entries (names only, to be created at Build time):
  - `LLM_API_KEY` (provider TBD — PRD Open Question)
  - `SERPER_API_KEY` (matching the reference implementation's `SerperDevTool` provider; PRD Open Question
    on whether to confirm this provider)

## 5. DevOps & Deployment Architecture

**CI/CD (minimal MVP)**: lint + unit tests + build only, per adapter-neutral defaults; no deployment
pipeline complexity beyond what Phase 3 (`@devops.eng`) defines.

**Hosting**: smallest MVP-appropriate target — a single-instance local or lightly-hosted Python process
(PRD §3 Infrastructure Specifications). A basic `GET /health` endpoint should exist for operational
sanity, even though PRD sets no uptime requirement.

**IaC / multi-region / advanced monitoring**: explicitly Future Work — not justified by PRD's
single-operator, non-commercial scope.

**Observability**: baseline logs (run start/stop, stage transitions, errors) and the Prompt
Trace/Trace Log described in §4. No APM/dashboarding tool is required for MVP.

## 6. Data Flow & Integration Architecture

1. Operator enters a job requisition in the chat UI → `POST /api/runs`.
2. Backend validates input, creates a `run_id`, and asynchronously invokes the CrewAI crew with the
   requisition as `inputs`.
3. `researcher` agent calls `SerperDevTool`/`ScrapeWebsiteTool` to source candidates → output passed via
   `Task.context` to `matcher`.
4. `matcher` scores/ranks candidates (same tool set, no LinkedIn scraping) → output passed to
   `communicator`.
5. `communicator` drafts outreach strategies/templates (draft-only, no send action) → output passed to
   `reporter`.
6. `reporter` synthesizes all three prior outputs into one markdown report; run status flips to
   `succeeded` with the report attached.
7. Chat UI polls/fetches `GET /api/runs/{run_id}` and renders the report; on any stage failure, status
   flips to `failed` with an error message surfaced in the chat (PRD §6).

**External integrations required for MVP only**: one LLM API, one web-search/scrape API (Serper by
default, per reference). No other third-party integration is in scope.

## 7. Performance & Scalability Specifications

- **Response-time target**: no hard SLA (PRD §5); a run is expected to take "on the order of minutes."
  The async job pattern in §4 exists specifically so this multi-minute duration doesn't force a blocking
  HTTP call.
- **Concurrency**: single operator, effectively one run at a time for MVP; no concurrent-run requirement
  designed for.
- **Scaling path**: explicitly deferred — no multi-tenant or horizontal-scaling design in this SAD,
  consistent with PRD §5 ("no fault-tolerance or scaling requirement for MVP").
- **Token/cost controls**: `max_rpm` at the crew level and the bounded candidate-list default (~10) are the
  primary cost controls (adapter rule "Execution"; PRD §7 Technical Metrics; MRD Risk Matrix).

## 8. Security & Compliance Architecture

- **AuthN/AuthZ**: none for MVP (single local/personal operator, PRD §3). If this service is ever exposed
  beyond localhost, authentication would need to be added first — flagged as an Open Question, not
  designed for here.
- **Secrets**: environment variables only; no secret values in Prompt Trace, Trace Log, or any
  `project-context/` artifact (adapter rule "Logging"/"Setup"; `aamad.config.yml`).
- **Input validation baseline**: required-field validation on run submission (§4); no other validation
  logic specified by PRD.
- **Third-party data exposure**: candidate data and job-requisition content pass through the LLM and
  search/scrape provider APIs during a run, even though nothing is persisted server-side. PRD flags this
  as unreviewed (PRD §5, Open Questions) — this SAD does not resolve it; it remains an Open Question for
  the operator to review those providers' data-handling terms before real candidate data is used.
- **Compliance**: no regulatory review performed (PRD §5) — explicitly deferred, not assumed compliant.
- **Security assessment**: required before Deliver per `aamad.config.yml`
  (`security.require_security_assessment: true`) — `@security.eng` must review before Phase 3, per
  `CHECKLIST.md` Step 5.5.

## 9. Testing & Quality Assurance Specifications

- **Unit tests**: agent/task YAML config loads without error; each declared tool is bindable; task
  `expected_output` fields are present; run-submission input validation (missing required fields is
  rejected) — mapped to PRD FR-1.
- **Integration tests**: full crew run end-to-end against FR-1…FR-5, using mocked/stubbed LLM and
  search/scrape tool responses to avoid real API cost and nondeterminism in CI; assert the final report
  contains sections corresponding to candidates, scores/justifications, and outreach drafts (PRD FR-5).
- **Smoke/acceptance**: one real (non-mocked) end-to-end run against a sample job requisition, verifying
  the async job pattern (`pending` → `running` → `succeeded`) and that the chat UI can submit a requisition
  and render the resulting report (PRD §6).
- **Runtime-specific checks**: validate Prompt Trace/Trace Log entries are produced per task (adapter rule
  "Logging"); validate no `LinkedInTool` (or equivalent) is bound to any agent, as a regression guard on
  the explicit MVP scope decision in PRD §3.
- **Security assessment**: recommended/required before Deliver, per §8 above.

## 10. MVP Launch & Feedback Strategy

- **Beta/pilot criteria**: N/A in the traditional sense — single operator is both the builder and the only
  user (PRD §2). "Launch" means the operator starts using the tool for real requisitions.
- **Success metrics tied to PRD KPIs** (PRD §7):
  - Recruiter time saved (hours/week) — no sourced baseline yet; the operator should begin self-logging
    manual-baseline time before or around first real use, per PRD §7/Open Questions.
  - Technical: a run completes end-to-end without manual intervention; candidate list stays within the
    bounded default.
  - UX: qualitative — operator finds each report actionable.
- **Iteration priorities after first real run**: revisit the async-job-vs-synchronous decision (§4) and
  the LLM/search-provider Open Questions (§4, §Open Questions below) based on actual run-time and cost
  observed.

## Implementation Guidance for AI Development Agents

1. **Foundation setup** (`@project.mgr`, `*setup-project`): scaffold repo structure, Python environment,
   `.env.example` with `LLM_API_KEY` / `SERPER_API_KEY` placeholder names (no values), per §4.
2. **Frontend MVP UI** (`@frontend.eng`, `*develop-fe`): build the single-page chat UI per §3, without
   backend wiring.
3. **Backend runtime scaffolding** (`@backend.eng`, `*develop-be`): implement `config/agents.yaml`,
   `config/tasks.yaml`, crew entrypoint per §2, and the `POST /api/runs` / `GET /api/runs/{run_id}` API per
   §4.
4. **Integration** (`@integration.eng`, `*integrate-api`): wire the chat UI to the run-submission/status
   API; verify the async status-polling round trip.
5. **QA** (`@qa.eng`): unit + integration + smoke tests per §9, mapped to PRD FR-1…FR-5.
6. **Security** (`@security.eng`): assessment per §8 before Deliver.
7. **Deliver** (`@devops.eng`): minimal deploy/CI/runbook per §5.

## Architecture Validation Checklist

- [x] PRD requirements mapped to architectural components (FR-1…FR-5 traced throughout §2–§6)
- [x] Agents designed for the domain and selected runtime (4-agent CrewAI sequential crew, §2)
- [x] Frontend and backend contracts agree on schemas — async job submit/poll contract defined in §4
- [x] Secrets via env vars only (§4, §8)
- [x] MVP vs. Future Work boundaries explicit (§1, throughout)
- [x] Resolved `AAMAD_TARGET_RUNTIME` recorded in Audit

## Sources

- `project-context/1.define/prd.md` (all sections, especially §3–§7)
- `project-context/1.define/mrd.md` (§2 Technical Feasibility, Risk Assessment Matrix)
- `.cursor/rules/adapter-crewai.mdc` (runtime-specific setup, execution, tools, logging, quality gates,
  failure policy, memory rules)
- `.cursor/rules/aamad-core.mdc` (cross-persona contracts: Sources/Assumptions/Open Questions/Audit,
  secrets handling, config precedence)
- `aamad.config.yml` (resolved `runtime.target: crewai`; security/testing/documentation gates)
- `.cursor/templates/sad-template.md` (this document's own template/instructions)

## Assumptions

- Frontend framework/library is unspecified by PRD and left to `@frontend.eng`'s discretion at Build time
  (§1, §3) — any lightweight chat-capable web stack satisfies this SAD.
- An async submit-then-poll API pattern (§4) is adopted as the MVP default over a single blocking call,
  based on the multi-minute run duration implied by PRD §5 — not an explicit PRD requirement, but an
  architecture decision made to avoid inventing a timeout failure mode PRD didn't ask for.
- Run state may be held in-process/in-memory only (no database), consistent with PRD's stateless-run
  decision; this means run state does not survive a backend process restart, which is acceptable for a
  single-operator MVP but should be confirmed, not assumed permanent.
- `max_iter <= 12`, `max_retry_limit >= 2`, and crew-level `max_rpm` are adopted from the adapter rule's
  baseline controls; PRD does not specify these values itself.

## Open Questions

- **LLM provider/model** (carried from PRD): still unresolved. This SAD's runtime-integration layer (§4) is
  provider-agnostic by design so this can be resolved at Build time without an architecture change.
- **Web-search provider** (carried from PRD): assumed to be Serper (matching the reference implementation)
  but not confirmed by the user.
- **Synchronous vs. async API pattern**: this SAD defaults to async submit/poll (§4) for robustness against
  multi-minute run times; confirm whether a simpler synchronous call is acceptable instead for a purely
  local, single-operator deployment.
- **Deployment exposure**: is this ever exposed beyond localhost (e.g., on a home network or small VPS)? If
  so, the "no AuthN/AuthZ for MVP" decision in §8 needs revisiting before that happens — not designed for
  in this SAD.
- **Third-party data-handling review** (carried from PRD): not resolved here; remains the operator's
  responsibility before real candidate data is processed.
- **Time-savings baseline** (carried from PRD §7): still not logged; affects §10's success-metric tracking
  but does not block architecture.

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `system-arch`
- **Action**: `create-sad`
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai` (from `aamad.config.yml`; no environment variable override
  observed)
- **Upstream artifacts**: `project-context/1.define/prd.md`, `project-context/1.define/mrd.md` (this
  session's prior artifacts)
