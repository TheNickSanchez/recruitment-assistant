# Product Requirements Document (PRD) — Recruitment Assistant

**Persona**: @product-mgr | **Action**: `*create-prd` | **Status**: Draft v1

## Input Requirements

**Deep Research Report / MRD**: `project-context/1.define/mrd.md` (this session)
**System Description**: Not present — `*elicit-requirements` was not run for this project; the user
directed `*create-mrd` → `*create-prd` directly, citing the CrewAI recruitment example as the reference
concept. Gaps this would normally have filled are recorded under Assumptions/Open Questions below.
**System Concept**: A personal, single-operator multi-agent assistant that takes one job requisition and
produces a candidate research + match/score + outreach-strategy + report pipeline, modeled on the CrewAI
"recruitment" example (`crewAIInc/crewAI-examples`, `crews/recruitment`), delivered behind a minimal chat
interface per this project's AAMAD conventions.
**Selected Runtime**: `crewai` (from `aamad.config.yml` → `runtime.target: crewai`).

## 1. Executive Summary

**Problem Statement**:
- The operator (a recruiter or hiring manager acting alone) wants to go from a job requisition to a
  ranked, justified candidate shortlist with ready-to-use outreach drafts, without manually running
  separate searches, scoring candidates by hand, and drafting messages one at a time.
- Impact is not quantified (no sourced data — see MRD §1); this is a personal productivity tool, not a
  commercial offering, so "target market" is N/A by design — scope is one operator, one requisition per run.

**Solution Overview**:
- A sequential 4-agent CrewAI pipeline — **Researcher → Matcher → Communicator → Reporter** — mirroring the
  reference example's `agents.yaml`/`tasks.yaml`/`crew.py`, exposed through a minimal chat interface: the
  operator submits a job requisition in chat and receives a formatted markdown report.
- Differentiator vs. the raw reference example: no LinkedIn cookie-scraping tool (dropped for MVP per the
  decision in §4 below); no CLI-only interaction (replaced with a chat interface per `AGENTS.md`'s
  `@frontend.eng` convention); explicit secrets handling per `aamad.config.yml`.
- Success outcome: a single run produces a usable, readable candidate report the operator would actually
  act on.

**Strategic Rationale**:
- A 4-stage sequential pipeline is a good fit because each stage's output is a hard input dependency for the
  next (you cannot score candidates that haven't been found; you cannot draft outreach for candidates that
  haven't been scored) — this is exactly `Process.sequential` with `Task(context=[...])` chaining, verified
  in the reference `crew.py`.
- No business case / ROI is claimed — personal tool, non-commercial (see MRD Executive Summary).

## 2. Market Context & User Analysis

**Target Market / Users**:
- Single persona: the project owner, acting as recruiter/hiring manager for their own open role(s).
  No market segment, geography, or expansion scope — **N/A, personal/internal tool** (per MRD §1 and the
  persona's own MRD-skip rule for internal tools).

**User Needs Analysis**:
- Needs one job requisition in → one structured report out, with the pipeline stages visible/traceable
  enough to trust the result (candidate list → scores/justification → outreach drafts → summary report).
- Adoption barriers: N/A (single, motivated user — the tool's author).

**Competitive Landscape**: Optional per template when MRD is thin — not benchmarked (see MRD §1).

## 3. Technical Requirements & Architecture

**Runtime & Agent Specifications** (aligned with `crewai`):
- **Collaboration pattern**: Sequential (`Process.sequential`), no hierarchical delegation
  (`allow_delegation=False` on every agent, per reference `crew.py`).
- **Orchestration**: 4 tasks chained by CrewAI's `Task(context=[...])` mechanism; the final `reporter` task
  receives the outputs of all three prior tasks as context, exactly as in the reference implementation.

**Core Agent Definitions** (adapted from the verified reference `agents.yaml`/`tasks.yaml`; MVP tool scope
differs — see decision below):

- **agent**: `researcher`
  **role**: "Job Candidate Researcher"
  **goal**: "Find potential candidates for the job"
  **tools**: `SerperDevTool` (web search), `ScrapeWebsiteTool` (page scraping) — **LinkedIn scraping tool
  dropped for MVP** (see decision below; reference implementation included a `LinkedInTool`)
  **expected output**: a bounded list (default: 10) of candidates with contact info and a brief
  suitability profile, per reference `research_candidates_task`.

- **agent**: `matcher`
  **role**: "Candidate Matcher and Scorer"
  **goal**: "Match the candidates to the best jobs and score them"
  **tools**: `SerperDevTool`, `ScrapeWebsiteTool`
  **expected output**: a ranked, scored, justified candidate list, per reference
  `match_and_score_candidates_task`. Note (carried verbatim from the reference task description as a real
  constraint, not an invented one): must not attempt to scrape LinkedIn profiles directly.

- **agent**: `communicator`
  **role**: "Candidate Outreach Strategist"
  **goal**: "Develop outreach strategies for the selected candidates"
  **tools**: `SerperDevTool`, `ScrapeWebsiteTool`
  **expected output**: outreach methods and message templates — **draft-only, no send capability** (MVP
  decision; see §4 Functional Requirements).

- **agent**: `reporter`
  **role**: "Candidate Reporting Specialist"
  **goal**: "Report the best candidates to the recruiters"
  **tools**: none (reference implementation gives `reporter` no tools; it synthesizes prior task context)
  **expected output**: a single markdown-formatted report consolidating candidates, scores/justifications,
  and outreach strategies, per reference `report_candidates_task`.

**MVP decision — LinkedIn tool dropped**: The reference repo's `LinkedInTool` (Selenium + `li_at` session
cookie) is **excluded from MVP scope**. Rationale: the reference README itself states this approach "may
violate LinkedIn's terms of service and could lead to your account being banned" and that the original
authors "do not endorse or encourage" real-world use of it — a verified statement from the source material.
Combined with `aamad.config.yml`'s `security.forbid_committed_secrets: true` (a session cookie is a
credential that would need careful, non-committed handling), the safer MVP default is to source candidates
via public web search/scraping only. This closes the MRD's corresponding Open Question. Re-adding an
authenticated LinkedIn integration is Future Work (§4, P2) and would require its own security/legal review.

**Integration Requirements**:
- Required external services: one LLM API (provider/model TBD — see Open Questions) and one web-search API
  (`SerperDevTool`'s backing provider, e.g. Serper.dev, matching the reference `.env.example` pattern).
- No database for MVP — each run is stateless; job requisition in, report out, nothing persisted server-side
  (mitigates the MRD's candidate-PII-retention Open Question by avoiding storage entirely at MVP scope).
- Auth: none for the chat interface at MVP (single local/personal operator); API keys for LLM/search
  supplied via environment variables per `aamad.config.yml`'s secret-handling rule.
- Performance target: a single run should complete within the time it takes 4 sequential LLM-driven agent
  tasks with web tool calls to execute — no hard SLA; this is a personal tool, not a service with uptime
  commitments.

**Infrastructure Specifications**:
- Single-instance local or lightly-hosted Python process (matches `language.primary: python` in
  `aamad.config.yml`).
- No dedicated compute/scaling tier — designed for one run at a time.
- Monitoring: basic run/console logging sufficient; no dedicated observability stack at MVP.

## 4. Functional Requirements

**Core Features (P0)**:
- **FR-1 — Submit job requisition**: As the operator, I can enter a job requisition (title, description,
  responsibilities, requirements, preferred qualifications, perks) into a chat interface and trigger a run.
  *Acceptance*: a submitted requisition starts the 4-agent pipeline and returns a final report without
  manual intervention between stages.
- **FR-2 — Candidate research**: The `researcher` agent returns a bounded candidate list (default 10) with
  contact info and a brief profile per candidate, sourced via web search/scrape tools only (no LinkedIn
  scraping in MVP).
- **FR-3 — Match & score**: The `matcher` agent produces a ranked list with a score and written
  justification per candidate, without attempting direct LinkedIn scraping (carried from reference task
  constraint).
- **FR-4 — Outreach strategy drafting**: The `communicator` agent produces outreach methods and message
  templates per candidate/segment. Draft-only — no message is actually sent to any candidate in MVP.
- **FR-5 — Consolidated report**: The `reporter` agent returns one markdown report combining candidates,
  scores/justifications, and outreach drafts, rendered in the chat interface.

**Enhanced Features (P1)** — deferred unless justified for MVP:
- None identified as necessary for MVP; the reference example's 4-stage pipeline is already complete for
  the stated intent.

**Future Features (P2)** — explicit Future Work:
- Authenticated LinkedIn sourcing (requires a dedicated legal/security review before any implementation).
- Actual outreach send capability (email/LinkedIn messaging), with associated anti-spam/compliance work.
- Persistent candidate/report storage across runs (requires a data-retention policy first).
- Multi-requisition batch runs / multi-user support.

## 5. Non-Functional Requirements

**Performance**: No hard response-time SLA; a single run is expected to take on the order of minutes given
sequential LLM + web-tool calls across 4 agents. Not benchmarked.

**Security & Compliance**:
- No secrets committed to the repository (`aamad.config.yml`: `security.forbid_committed_secrets: true`);
  LLM/search API keys via environment variables only.
- Security assessment required before Deliver (`security.require_security_assessment: true`) —
  `@security.eng` must review before Phase 3.
- No candidate PII is persisted server-side at MVP (stateless run design — see §3), which limits data-
  protection exposure but does not eliminate it (candidate data still passes through LLM/search-provider
  APIs during a run — provider data-handling terms are an Open Question, not yet reviewed).
- Regulatory compliance (e.g., candidate-data handling regulations) not reviewed — flagged, not assumed.

**Scalability & Reliability**: Single-run, single-operator scope; no fault-tolerance or scaling requirement
for MVP. If a stage fails, the run fails — no retry/resume logic specified for MVP (Future Work if needed).

## 6. User Experience Design

**Interface Requirements**:
- Minimal chat interface (per `AGENTS.md`'s `@frontend.eng`: "Builds MVP chat interface"; `aamad.config.yml`
  → `ui.visual_style: minimal`, `ui.theme: system`).
- Web-based, no dedicated mobile requirement.
- No specific accessibility standard mandated beyond following the minimal chat UI's default conventions;
  not a formal requirement for MVP.

**Agent Interaction Design**:
- Operator interacts once per run: submit requisition, receive report. No mid-pipeline approval gate for
  MVP (matches reference implementation's fully-automated sequential flow).
- Errors (e.g., a failed tool call or LLM error mid-pipeline) should surface to the operator in the chat
  rather than fail silently; specific error-message format is a Build-phase (`@integration.eng`) decision.
- Transparency: the final report should retain visibility into how each candidate was sourced/scored, not
  just a bare ranked list, matching the reference `expected_output` requirements for each task.

## 7. Success Metrics & KPIs

**Business / Operational Metrics**:
- **Recruiter time saved, in hours/week** `[Target metric — no sourced baseline; see Assumptions/Open
  Questions]`. Defined as: `(manual baseline hours/week for sourcing + screening + outreach drafting) −
  (operator hours/week spent per run × runs/week, post-adoption)`.
  - **Manual baseline**: not sourced from industry data this session (MRD §1 notes the `WebSearch` tool was
    unavailable and no figure was substituted from memory). The operator should self-log their own pre-tool
    baseline (hours spent per requisition on research, scoring, and drafting outreach by hand) before/around
    MVP rollout so the metric has a real personal baseline to compare against, rather than an industry
    average that wasn't independently verified.
  - **Target (provisional, not sourced)**: reduce operator hands-on time per requisition from a manual
    baseline to primarily the time spent (a) writing the job requisition and (b) reading/acting on the
    final report — i.e., most of the research/scoring/drafting time should shift from the operator to the
    pipeline. No specific hours/week number is committed here since no baseline exists yet; this is
    recorded as an Open Question below.
  - **How measured for MVP**: operator self-reports elapsed wall-clock time per run (pipeline execution
    time) plus their own time spent reviewing/acting on the report; compared against their self-logged
    manual baseline. No automated time-tracking instrumentation is in scope for MVP.

**Technical Metrics**:
- A run completes end-to-end (all 4 tasks succeed) without manual intervention.
- Candidate list size stays within the bounded default (~10) to control LLM/search cost, per MRD Risk
  Matrix (Medium Risk: unbounded cost exposure).

**User Experience Metrics**:
- Qualitative only: the operator finds the report usable enough to act on. No quantitative target sourced
  (see MRD §3).

## 8. Implementation Strategy

**Development Phases**:
- **Phase 1 (Define)**: MRD (this session) → PRD (this document) → SAD (next: `@system.arch`).
- **Phase 2 (Build)**: `@project.mgr` setup → `@frontend.eng` (chat UI) / `@backend.eng` (CrewAI pipeline
  per `AAMAD_TARGET_RUNTIME=crewai`) → `@integration.eng` (wire chat ↔ crew) → `@qa.eng` (unit + integration
  tests, mapped to FR-1…FR-5 per `aamad.config.yml`'s `testing.map_to_acceptance_criteria: true`) →
  `@security.eng` (required per config before Deliver).
- **Phase 3 (Deliver)**: `@devops.eng` — deploy runbook + user guide (`documentation.require_user_guide:
  true` in `aamad.config.yml`).

**Resource Requirements**: One developer (project owner) across all Build roles; LLM API key; web-search
API key (e.g., Serper). No dedicated infra budget beyond API usage costs.

**Risk Mitigation**: See MRD Risk Assessment Matrix — highest risk (LinkedIn ToS exposure) already mitigated
by dropping that tool from MVP scope (§3 above); remaining risks (cost exposure, scrape reliability) are
accepted at MVP scale given the bounded candidate-list default.

## 9. Launch & Go-to-Market Strategy

**N/A** — personal, internal tool; no go-to-market plan. (Recorded here rather than fabricated, per
Assumptions.)

## Quality Assurance Checklist

- [x] Requirements traceable to MRD, the verified reference repository, or recorded Assumptions
- [x] Technical specifications feasible with the `crewai` runtime adapter (directly modeled on a working
  reference implementation)
- [x] Success metrics aligned with stated objectives (qualitative personal-utility metrics, plus one
  quantitative time-savings metric added at user request — baseline not yet sourced, see Open Questions)
- [x] MVP vs. Future Work boundaries explicit (§4)
- [x] Market sections marked N/A given the MRD's internal-tool scope reduction

## Sources

- `project-context/1.define/mrd.md` (this session's MRD, §Sources for full citation list).
- `crewAIInc/crewAI-examples`, path `crews/recruitment` (agents.yaml, tasks.yaml, crew.py, main.py,
  linkedin.py, README.md) — fetched directly via `gh api` during this session; treated as the primary
  technical reference.
- This project's `aamad.config.yml` and `AGENTS.md` (repo-local).
- `.cursor/templates/prd-template.md` (this document's own template/instructions).

## Assumptions

- No `system-description.md` was elicited; the user's explicit instruction to run `*create-mrd` then
  `*create-prd` directly (citing the CrewAI example by name) is treated as sufficient system concept input,
  per persona guidance that elicitation is preferred but not mandatory when the use case is well-specified
  by a known reference.
- MVP interface is a chat UI, not a bare CLI, inferred from `AGENTS.md`'s `@frontend.eng` role description
  ("Builds MVP chat interface") rather than from an explicit user statement — flagged here in case the user
  actually wants to keep the reference's CLI-only interaction model.
- LinkedIn sourcing is dropped for MVP (see §3 decision) — this resolves the MRD's corresponding Open
  Question with a specific product choice rather than leaving it open; the user should confirm this
  disposition.
- Draft-only outreach (no send capability) is assumed for MVP to avoid taking on anti-spam/compliance scope
  not present in the reference implementation.
- No database/persistence layer for MVP; each run is stateless.
- The hours/week time-savings metric (§7) added at explicit user request has no sourced manual-baseline
  figure; the operator's own self-logged pre-tool time is assumed to serve as the baseline rather than an
  industry average, since no industry figure was independently verified this session (see MRD §1 tooling
  note). No automated time-tracking is assumed for MVP — self-reported only.

## Open Questions

- **LLM provider/model**: The reference repo defaults to GPT-4o; this project's runtime choice (`crewai`)
  does not itself pin a model. Which LLM provider/model should `@backend.eng` target for Build?
- **Web-search provider**: Reference uses Serper (`SerperDevTool`) — confirm this is the intended provider
  for this project, or specify an alternative.
- **Candidate data handling with third-party APIs**: Even without server-side storage, candidate data passes
  through LLM and search-provider APIs during a run. Has the operator reviewed those providers' data-
  handling terms for this use case? Not reviewed in this document.
- **Confirm LinkedIn-drop decision**: The Assumptions above resolve this in favor of dropping LinkedIn
  sourcing for MVP — the user should explicitly confirm or override this before `@system.arch` proceeds to
  SAD, since it changes the agent's tool list relative to the named reference example.
- **Time-savings target number**: What manual baseline (hours/week the operator currently spends
  sourcing/screening/drafting outreach by hand) should be logged before/around MVP rollout, and what target
  hours/week reduction is realistic? Not set here — no sourced baseline exists (see §7, Assumptions).
- **Confirm chat-UI assumption**: Should the MVP genuinely be a chat interface (per `AGENTS.md` convention)
  or a closer CLI port of the reference example?

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `product-mgr`
- **Action**: `create-prd`
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai` (from `aamad.config.yml`)
- **Upstream artifact**: `project-context/1.define/mrd.md` (this session)
- **Revision**: 2026-08-20 — added a recruiter time-savings (hours/week) success metric to §7 at explicit
  user request; no sourced baseline available, recorded as Assumption + Open Question rather than a
  fabricated target number.
