# Market Research Document (MRD) — Recruitment Assistant

**Persona**: @product-mgr | **Action**: `*create-mrd` | **Status**: Draft v1

## Context & Instructions

This project is a **personal, non-commercial** multi-agent system modeled on the public CrewAI "recruitment" example
(`crewAIInc/crewAI-examples`, path `crews/recruitment`, default branch `main`). It automates candidate research,
matching, outreach-strategy drafting, and reporting for a single operator (a recruiter or hiring
manager acting on their own behalf), not a multi-tenant commercial product.

**Scope deviation from the standard MRD Research Quality Requirements (15–20 sources, market-sizing
rigor)**: this environment's web-search tool was unavailable during this session (see Sources), and this
document intentionally does not fabricate market-sizing statistics, TAM/SAM figures, or competitive
benchmarks that could not be verified against a live source. Per the persona's own operating rule
("MRD is optional for internal/personal/operational tools; when skipped, record rationale under PRD
Assumptions"), the market-facing dimensions below (§1 and parts of §5) are intentionally thin and marked
`[Unverified — general knowledge, not sourced]` rather than presented as sourced findings. The
technical-feasibility, UX, and production dimensions (§2–§4) are grounded in the actual example repository,
which was fetched and read directly, and are treated as verified.

## Research Query Structure

**Primary Focus**: Personal AI recruitment assistant — automates candidate sourcing, matching/scoring,
outreach-strategy drafting, and reporting from a single job requisition, for one operator.
**Example**: CrewAI "recruitment" example crew (`crews/recruitment` in `crewAIInc/crewAI-examples`).
**Selected Runtime**: `crewai` (per `aamad.config.yml` → `runtime.target: crewai`).

## Research Dimensions

### 1. Market Analysis & Opportunity Assessment `[Unverified — general knowledge, not sourced; not load-bearing for an internal tool]`

- **Market Size / Growth Trends**: Not researched with a live source this session; not applicable to
  project scope — this is a personal tool, not a product being brought to market. Do not use any figure
  here for planning purposes.
- **Market Gaps**: Commercial ATS/sourcing tools (e.g., LinkedIn Recruiter, Greenhouse, generic sourcing
  SaaS) are subscription-priced and built for team/enterprise use; a lightweight, self-hosted, single-operator
  agent crew is a plausible personal alternative for ad hoc or low-volume hiring, but this claim is
  qualitative, not measured.
- **Target Audience**: One persona — an individual recruiter or hiring manager running searches for their
  own open roles, comfortable running a local Python app and supplying API keys.
- **Business Case**: N/A — no ROI/pricing model; success is measured by personal utility (see §3).
- **Competitive Landscape**: Not benchmarked. Adjacent categories exist (ATS platforms, LinkedIn Recruiter,
  sourcing extensions) but no feature-by-feature comparison was performed.

**Implication for design**: Do not gate MVP scope on market validation. Treat this dimension as informational
context only; all commitments in the PRD derive from §2–§4 below and from the reference implementation.

### 2. Technical Feasibility & Requirements Analysis `[Verified against crewAIInc/crewAI-examples, path crews/recruitment, branch main]`

- **Runtime Capabilities**: CrewAI's `Process.sequential` crew model directly fits a 4-stage pipeline
  (research → match/score → outreach strategy → report) where each stage's output feeds the next via
  `Task(context=[...])`. This is exactly the pattern used by the reference crew's `report_candidates_task`,
  which declares `context=[research_candidates_task(), match_and_score_candidates_task(),
  outreach_strategy_task()]`.
- **Agent Architecture Pattern**: 4 single-purpose agents, each `allow_delegation=False`: `researcher`,
  `matcher`, `communicator`, `reporter`. No hierarchical manager agent; orchestration is purely sequential
  task-chaining, not agent-to-agent delegation.
- **Integration Requirements (from reference repo)**:
  - `SerperDevTool` (web search) — used by `researcher`, `matcher`, `communicator`.
  - `ScrapeWebsiteTool` — used by `researcher`, `matcher`, `communicator`.
  - A custom `LinkedInTool` (Selenium-based, authenticates via a `li_at` session cookie) — used only by
    `researcher` in the reference implementation.
  - LLM: reference README states GPT-4o by default; runtime-agnostic per this project's
    `AAMAD_TARGET_RUNTIME` convention — the LLM/runtime choice is a Build-phase decision, not fixed here.
- **Technical Risk — flagged, not carried into MVP scope by default**: the reference repo's own README
  contains an explicit disclaimer that LinkedIn cookie-based scraping "may violate LinkedIn's terms of
  service and could lead to your account being banned" and states the authors "do not endorse or encourage
  the use of this tool for any real-world applications." This is a verified statement from the source
  material, not an inference. See PRD Open Questions for the resulting scope decision.
- **Scalability Considerations**: Single-run, single-operator, low-volume (reference task expects "a list of
  10 potential candidates" per run) — no concurrency or multi-tenant scaling requirement for MVP.
- **Infrastructure Needs**: Local/single-instance Python process; outbound calls to an LLM API and a search
  API (e.g., Serper); no database required for MVP (see PRD §3, Infrastructure Specifications).

**Implication for design**: The reference architecture (4 sequential agents/tasks) is directly reusable.
The LinkedIn-scraping tool is not reusable as-is without a deliberate, informed risk decision — see Open
Questions.

### 3. User Experience & Workflow Analysis `[Verified against reference repo where noted; otherwise reasoned from AAMAD conventions]`

- **User Journey**: Operator supplies a job requisition (title, description, responsibilities, requirements,
  preferred qualifications, perks) → crew runs research → match/score → outreach strategy → consolidated
  report is returned to the operator. This mirrors the reference `main.py`'s `job_requirements` input and the
  `report_candidates_task` output.
- **Interface Requirements**: The reference example is a CLI script (`poetry run recruitment`). Per this
  project's AAMAD conventions (`AGENTS.md`, `@frontend.eng` role: "Builds MVP chat interface"), the MVP for
  this project should present a minimal chat-style interface where the operator pastes/enters a job
  requisition and receives the report — not a bare CLI, and not a full ATS UI.
- **Automation vs. Human-in-the-Loop**: All four stages are fully automated in the reference crew; the human
  is in the loop only at the start (submitting requirements) and the end (reading the report and acting on
  outreach). No approval gate exists mid-pipeline in the reference implementation.
- **Success Metrics (qualitative, personal-use)**: operator judges the candidate list and report as useful
  enough to act on; no quantitative target is sourced.
- **Adoption Factors**: Single user (the project owner) — adoption is not a variable; usability and
  correctness of a single run are what matter.

### 4. Production & Operations Requirements `[Reasoned from aamad.config.yml + reference repo; not independently market-researched]`

- **Deployment Architecture**: Single-instance local or lightly-hosted Python process; no multi-region or
  HA requirement for a personal tool.
- **Monitoring & Observability**: Basic run logs sufficient for MVP; no SLO/alerting requirement.
- **Security Considerations**: `aamad.config.yml` sets `security.require_security_assessment: true` and
  `forbid_committed_secrets: true` — API keys (LLM, search provider, and any credential-based tool) must be
  supplied via environment variables / secret store, never committed. This directly conflicts with the
  reference repo's pattern of a LinkedIn session cookie in `.env` if that tool is retained — see PRD Open
  Questions.
- **Maintenance**: Personal project; no formal update/versioning SLA.
- **Cost Structure**: Variable LLM + search-API token/call costs per run; not quantified here (depends on
  provider and volume, which are Build-phase/runtime decisions).
- **Risk Assessment**: See Risk Matrix below.

### 5. Innovation & Differentiation Analysis `[Mostly Unverified — general reasoning, not sourced]`

- **Unique Value Proposition**: Not a novel technique — this project's value is personal automation and a
  learning vehicle for the AAMAD multi-agent workflow, not market differentiation.
- **Emerging Technologies**: N/A for MVP scope.
- **Patent Landscape / Partnerships / Monetization**: N/A — non-commercial, personal use only. Recorded as
  Assumption, not researched.

## Executive Summary

**Market Opportunity**: Not assessed with sourced data this session; not load-bearing for a personal,
non-commercial tool (see §1 scope deviation above).

**Technical Feasibility**: High. The reference CrewAI recruitment example (`crewAIInc/crewAI-examples`,
`crews/recruitment`) provides a directly verifiable, working 4-agent/4-task sequential pipeline
(`researcher` → `matcher` → `communicator` → `reporter`) that fits this project's stated intent and the
`crewai` runtime already selected in `aamad.config.yml`. The main open technical/ethical decision is whether
to retain the reference implementation's LinkedIn cookie-scraping tool, which the source material itself
flags as a Terms-of-Service risk.

**Recommended Approach**: Reuse the reference crew's agent/task decomposition and sequential process model.
Descope or replace the LinkedIn-scraping tool for MVP (recommend: replace with `SerperDevTool` +
`ScrapeWebsiteTool` only, sourcing from public web/job-board data, and resolve the LinkedIn question
explicitly before Build — see PRD Open Questions). Deliver a minimal chat interface over the crew, consistent
with `@frontend.eng`'s "MVP chat interface" convention in `AGENTS.md`.

## Critical Decision Points

- **Go/No-Go Factor**: None — this is a personal/internal tool; there is no commercial viability gate.
- **Technical Architecture Choice**: Sequential CrewAI process with 4 single-purpose agents, matching the
  reference implementation; confirmed feasible.
- **Market Positioning**: N/A.
- **Resource Requirements**: One developer (the project owner), LLM API access, one web-search API
  (e.g., Serper) — consistent with reference repo's `.env.example` pattern.

## Risk Assessment Matrix

- **High Risk**: Reusing the reference repo's LinkedIn Selenium/cookie-based scraping tool as-is — the
  source README itself states this may violate LinkedIn's Terms of Service and risks account bans. Must be
  resolved as an explicit Open Question before Build (see PRD).
- **Medium Risk**: LLM/search-API cost exposure is unbounded per run if the operator supplies very broad job
  requirements (reference task expects a bounded "list of 10" candidates, which should be preserved as a
  guardrail).
- **Medium Risk**: Scraped web/job-board content quality and rate limits are outside this project's control.
- **Low Risk**: Local single-instance deployment has minimal operational risk given no multi-tenant or
  high-availability requirement.

## Actionable Recommendations

- **Immediate Next Steps (within 48 hours)**: Resolve the LinkedIn-tool Open Question (retain with informed
  risk acceptance vs. drop) before drafting the PRD's Core Agent Definitions in detail.
- **Short-term Priorities (next 30 days)**: Build the 4-agent sequential crew against the `crewai` runtime,
  wrapped in a minimal chat interface; keep candidate-list size bounded (reference default: 10).
- **Long-term Strategy**: Not applicable beyond MVP — this is a personal tool; no roadmap commitments made
  here (future ideas, if any, belong in PRD §4 Future Features).

## Research Quality Requirements — Deviation Note

The standard 15–20-source, quantitative-evidence bar in this template is intended for commercial MRDs. This
document deliberately does not meet that bar for the market-facing dimension (§1) because (a) this is a
personal/internal tool per the persona's own skip-rationale rule, and (b) no live web-search tool was
available in this session to source such figures honestly. The technical dimension (§2) is instead grounded
in one high-confidence primary source: the actual reference repository content, fetched and read directly
via the GitHub API rather than inferred from memory.

## Sources

1. `crewAIInc/crewAI-examples` GitHub repository, path `crews/recruitment` (branch `main`, repo currently
   archived; fetched via `gh api repos/crewAIInc/crewAI-examples/...` during this session):
   - `crews/recruitment/README.md`
   - `crews/recruitment/src/recruitment/config/agents.yaml`
   - `crews/recruitment/src/recruitment/config/tasks.yaml`
   - `crews/recruitment/src/recruitment/crew.py`
   - `crews/recruitment/src/recruitment/main.py`
   - `crews/recruitment/src/recruitment/tools/linkedin.py`
2. This project's own `aamad.config.yml` and `AGENTS.md` (repo-local, read directly).
3. `.cursor/templates/mrd-template.md` (this document's own template/instructions).

**Not sourced this session** (attempted and unavailable): live web search for AI-recruiting market size,
CAGR, or time-to-hire industry statistics — the session's `WebSearch` tool returned repeated API errors, and
a fallback attempt via `WebFetch` against a search-engine results page returned no extractable content
(search engines require JS rendering that the fetch tool cannot execute). No figures were substituted from
model memory in place of a verified source.

## Assumptions

- This is a personal, non-commercial, single-operator tool; market sizing, competitive benchmarking, and
  monetization are out of scope by the persona's own MRD-skip rule for internal tools, even though the user
  explicitly requested `*create-mrd` be run (honored above with reduced market-dimension depth rather than
  skipped entirely).
- The `crewai` runtime target from `aamad.config.yml` is authoritative for this document; no alternative
  runtime was evaluated.
- Candidate list size of ~10 per run (from the reference task's `expected_output`) is assumed as a reasonable
  MVP default guardrail, not a hard requirement.
- No compliance/regulatory review (e.g., EEOC, GDPR candidate-data handling) was performed; flagged as an
  Open Question, not assumed away.

## Open Questions

- **LinkedIn scraping tool**: Retain a LinkedIn-cookie-based sourcing tool (with informed ToS/account-risk
  acceptance by the operator) or drop it for MVP in favor of `SerperDevTool` + `ScrapeWebsiteTool` only?
  This must be resolved before the PRD's Core Agent Definitions are finalized.
- **Candidate PII handling**: What retention/storage policy applies to sourced candidate names, contact
  info, and profile data once a report is generated? No storage layer exists in the reference implementation
  (in-memory, single run).
- **LLM/runtime provider**: Reference repo defaults to GPT-4o; this project's `AAMAD_TARGET_RUNTIME=crewai`
  does not itself pin an LLM provider — which provider/model should Build target?
- **Outreach execution**: The reference `communicator` agent only *drafts* outreach strategy/templates — it
  does not send messages. Confirm MVP stays at draft-only (recommended) vs. adding actual send capability
  (email/LinkedIn), which would raise new compliance and anti-spam considerations.

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `product-mgr`
- **Action**: `create-mrd`
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai` (from `aamad.config.yml`)
- **Tooling note**: `WebSearch` unavailable (repeated tool errors this session); `WebFetch` against a
  search-engine results page returned no usable data; GitHub reference data retrieved successfully via
  `gh api`.
