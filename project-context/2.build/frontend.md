# Frontend Implementation — Recruitment Assistant

**Persona**: @frontend-eng | **Action**: `*develop-fe` (includes `*add-placeholders`, `*style-ui`,
`*document-frontend`) | **Status**: MVP implemented

## Input Requirements

**PRD**: `project-context/1.define/prd.md` (Draft v1, revised 2026-08-20 — 3-agent design)
**SAD**: `project-context/1.define/sad.md` (Draft v2, revised 2026-08-20 — §3 Frontend Architecture
Specification, §6 Data Flow)
**setup.md**: `project-context/2.build/setup.md` — **does not exist**, same gap already recorded by
`@backend.eng` in `backend.md`. `@project.mgr`'s `*setup-project` was not run. Per `aamad-core.mdc` this is
recorded as an Assumption below rather than blocking — SAD §3 already specifies the minimum requirement
(single page, requisition form, markdown report rendering) precisely enough to scaffold without it.

## What Was Built

### Stack decision

SAD §3 explicitly leaves the frontend framework to this persona's discretion ("no single vendor UI library
is hardcoded"). Per `.cursor/agents/frontend-eng.md`'s own action list (`*develop-fe` — "Implement chat UI
in **Next.js**" / `*style-ui` — "Use **Tailwind**"), the framework choice is not actually open — built with
**Next.js 16 (App Router) + TypeScript + Tailwind CSS v4**, scaffolded via `create-next-app`.

### Directory layout

```
frontend/
  src/
    app/
      layout.tsx        Root layout, page metadata
      page.tsx           Single route (SAD §3: "Single route/page for MVP")
      globals.css         Tailwind + typography plugin import
    components/
      RequisitionForm.tsx    Job requisition input (title, description + collapsible
                              responsibilities/requirements/preferred_qualifications/perks/candidate_count)
      ChatMessage.tsx         Renders one chat turn: user's requisition, or assistant's
                              loading/error/markdown-report bubble
      FutureFeaturesPanel.tsx Visual-only stubs for P2 features (run history, LinkedIn sourcing,
                              send outreach, batch runs) — *add-placeholders* action
    lib/
      types.ts              TypeScript mirror of backend/app/models.py's Pydantic models
      runClient.ts            STUB submit/poll client — see "Backend connection" below
```

### Interface Requirements (SAD §3) — coverage

- **Chat-style input + report display**: `page.tsx` renders a scrolling message list
  (`ChatMessage` per turn) with the `RequisitionForm` pinned to the bottom, chat-app style.
- **Loading state**: required by SAD §3 ("a run takes on the order of minutes") — implemented as an
  animated "thinking" bubble with distinct copy for `pending` vs `running` status.
- **Error state**: required by SAD §3 / PRD §6 ("errors... surface to the operator in the chat rather than
  fail silently") — implemented as a red error bubble rendering the `{code, message}` error envelope shape
  from `RunErrorEnvelope` (`backend/app/models.py`), not a generic toast/alert.
- **Report rendering**: the `recommender` agent's output is markdown (PRD FR-4 — two sections,
  `## Recommendations` / `## Outreach Guidance`) — rendered via `react-markdown` + `remark-gfm` +
  Tailwind's `@tailwindcss/typography` plugin so headings/lists/tables/bold render correctly, not as raw
  text.
- **Placeholders for Future Work** (optional per SAD §3, but in scope per this persona's
  `*add-placeholders` action): `FutureFeaturesPanel` lists the PRD §4 P2 deferrals (run history,
  authenticated LinkedIn sourcing, outreach send, multi-requisition batch) as visibly disabled
  (`aria-disabled`, dashed border, no click handler) — non-functional by design, not hidden functionality.
- **Responsive/accessibility**: not mandated by PRD; the layout collapses the future-features sidebar
  below the `lg` breakpoint and the form fields stack on narrow viewports as a baseline, without a formal
  a11y audit (none required).

### Backend connection — deliberately NOT wired

Per this persona's own `prohibited-actions` (`.cursor/agents/frontend-eng.md`): *"Implement backend
connection (leave to integration agent)"*. `src/lib/runClient.ts` is an explicit, clearly-commented **stub**
that fakes the SAD §4 async submit/poll contract (`POST /api/runs` → `{run_id, status}`,
`GET /api/runs/{run_id}` → `{run_id, status, report, error, ...}`) entirely client-side:

- `submitRun()` resolves with a fake `run_id` after a short delay.
- `pollRun()` returns `status: "running"` for the first ~2.6s of simulated elapsed time, then
  `status: "succeeded"` with a canned two-section markdown report (or could be made to return `"failed"`
  for manual testing of the error bubble).
- `src/lib/types.ts` mirrors `backend/app/models.py`'s Pydantic models field-for-field, so
  `@integration.eng` can drop in real `fetch("/api/runs", ...)` calls against those exact shapes without
  touching any component — `page.tsx`, `ChatMessage.tsx`, and `RequisitionForm.tsx` only depend on the
  `JobRequisition` / `RunResultResponse` / `RunSubmissionResponse` types, not on `runClient.ts` being real.

**Traceability note (adapter rule, per this persona's Workflow Notes)**: because the pipeline is
non-streaming (SAD §1) and the UI instead polls for status, the loading bubble intentionally shows a single
generic "in progress" message rather than per-agent-stage progress — the SAD's data contract (§4) does not
expose per-stage status (`researcher` vs `evaluator` vs `recommender`), only overall run status. If
per-stage visibility is wanted later, that's a backend contract change (new field on
`RunResultResponse`), not a frontend-only addition.

## Verification Performed

- `npm run lint` — 0 errors, 0 warnings.
- `npm run build` (production build, Turbopack) — compiles successfully, static page generated for `/`.
- `npm run dev` — started `next dev`, confirmed `GET /` returns `200` with the expected page title/heading
  server-rendered.
- Did **not** perform interactive browser testing (no browser/screenshot tool available in this session) —
  verified the component tree compiles and type-checks, and that the initial server-rendered markup is
  correct, but did not click through the submit → loading → report flow in an actual browser. Flagged as an
  Open Question / QA follow-up below.

## Known Gaps / Non-MVP Stubs

- No real backend connection (by design — see above; `@integration.eng`'s scope).
- No interactive browser verification performed this session (see Verification Performed).
- No accessibility audit beyond basic responsive layout.
- `FutureFeaturesPanel` items are static, hand-authored from PRD §4 P2 — not derived from any shared
  feature-flag config; if P2 scope changes, this list needs manual updating.

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/sad.md`
- `.cursor/agents/frontend-eng.md`
- `backend/app/models.py` (API contract shapes mirrored in `frontend/src/lib/types.ts`)

## Assumptions

- `project-context/2.build/setup.md` does not exist; proceeded directly per SAD §3's already-specific
  minimum requirement, matching `@backend.eng`'s precedent in `backend.md`.
- Next.js (App Router) + Tailwind was treated as effectively fixed by `.cursor/agents/frontend-eng.md`'s
  action descriptions, not an open choice left purely to this persona's taste.
- The mock report shape (two `##` sections) in `runClient.ts` matches the `recommend_candidates_task`
  `expected_output` constraint already enforced by `backend/tests/test_config.py`, so the UI's markdown
  rendering is exercised against a realistic shape even without a real backend call.
- Per-stage pipeline progress is out of scope for the frontend until/unless the backend contract exposes it
  (see Traceability note above).

## Open Questions

- **Interactive browser verification**: should be performed by `@integration.eng` or `@qa.eng` once wired
  to the real backend (or manually via `npm run dev` + a browser) — not done in this session.
- **Per-stage progress visibility**: would the operator want to see which of the 3 agents is currently
  running, rather than one generic "in progress" indicator? Would require a SAD/backend contract change,
  not just a frontend addition.
- **Streaming**: SAD §1 fixes non-streaming for MVP; unchanged here, but if that's revisited, the polling
  loop in `page.tsx`/`runClient.ts` would need to become a streaming subscription instead.

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `frontend-eng`
- **Action**: `develop-fe` (`add-placeholders`, `style-ui`, `document-frontend`)
- **Stack**: Next.js 16.3.1 (App Router, TypeScript), Tailwind CSS v4 + `@tailwindcss/typography`,
  `react-markdown` + `remark-gfm`.
- **Upstream artifacts**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`,
  `backend/app/models.py` (contract shapes only — no runtime import/dependency on the backend).
- **Test results**: `npm run lint` clean; `npm run build` succeeds; `npm run dev` smoke-checked via
  `curl` (no interactive browser session available).
