# Integration — Recruitment Assistant

**Persona**: @integration-eng | **Action**: `*integrate-api` (includes `*verify-messageflow`,
`*log-integration`) | **Status**: MVP wired, verified end-to-end (failure path)

## Input Requirements

**PRD**: `project-context/1.define/prd.md` (Draft v1, revised 2026-08-20 — 3-agent design)
**SAD**: `project-context/1.define/sad.md` (Draft v2, revised 2026-08-20 — §3 Frontend, §4 Backend, §6 Data
Flow)
**frontend.md**: `project-context/2.build/frontend.md` — chat UI built, backend connection deliberately left
as a stub (`src/lib/runClient.ts`) per `@frontend.eng`'s own prohibited-actions.
**backend.md**: `project-context/2.build/backend.md` — FastAPI backend implemented per SAD §4
(`POST /api/runs`, `GET /api/runs/{run_id}`, `GET /health`).
**setup.md**: does not exist (same gap already recorded by both `@frontend.eng` and `@backend.eng` — no
`@project.mgr` `*setup-project` run for this project). Not blocking: SAD §3/§4 and the two Build docs already
fix every contract detail (endpoint shapes, request/response schemas, framework choices) needed to wire the
two sides together.
**Selected Runtime**: `crewai` (unaffected by this integration layer — the API contract is the same
regardless of runtime; see SAD §4 "provider-agnostic by design").

## What Was Built

### Runtime interoperability assumptions validated

Per this persona's `instructions` (validate endpoint contract, payload schema, streaming/non-streaming
behavior, error envelope shape) — all four checked directly against the running backend, not just read from
docs:

- **Endpoint contract**: `POST /api/runs` (202, body `{run_id, status}`) and `GET /api/runs/{run_id}` (200,
  body `{run_id, status, created_at, updated_at, report, error}`) match SAD §4 exactly; confirmed live via
  `curl` (see Verification Performed) before touching frontend code.
- **Payload schema**: `frontend/src/lib/types.ts`'s `JobRequisition` (`title`, `description`,
  `responsibilities`, `requirements`, `preferred_qualifications`, `perks`, `candidate_count`) is
  field-for-field identical to `backend/app/models.py`'s `JobRequisition` — no shape translation needed
  between `RequisitionForm`'s submitted object and the `POST /api/runs` request body.
- **Streaming vs. non-streaming**: confirmed non-streaming, matching SAD §1 — the frontend's existing
  submit-then-poll loop (`page.tsx`) required no restructuring, only a real client underneath it.
- **Error envelope shape**: two distinct shapes exist and both are now handled:
  1. FastAPI's default `422` validation-error body (`{"detail": [...]}, `) for malformed/missing-field
     submissions — not the custom envelope. `runClient.ts` detects this shape and maps it to
     `{code: "validation_error", message: "<joined msgs>"}` so the UI's single `RunErrorEnvelope`-shaped
     `ErrorBubble` component didn't need a second code path.
  2. SAD §4's custom `{code, message}` envelope for run-failure states (e.g. `pipeline_error`) — passed
     through unchanged from `GET /api/runs/{run_id}`'s `error` field.
  A third case neither doc anticipated as a distinct envelope — **network failure** (backend unreachable,
  DNS/connection refused) — is mapped to a synthesized `{code: "network_error", message: "<fetch error>"}`
  so a downed backend surfaces in the chat rather than an unhandled promise rejection. This is an
  integration-layer addition, not a backend contract change.

### Frontend changes (`frontend/`)

- **`src/lib/runClient.ts`** — replaced the stub (fake timers, canned markdown) with a real client:
  `submitRun()` does `POST {API_BASE_URL}/api/runs`, `pollRun(run_id)` does
  `GET {API_BASE_URL}/api/runs/{run_id}`. Both throw a new `RunClientError` (carries a `RunErrorEnvelope`)
  on any non-2xx response or network failure, rather than the stub's always-succeeds behavior.
- **`API_BASE_URL`** — read from `NEXT_PUBLIC_API_URL` (Next.js client-exposed env var), defaulting to
  `http://localhost:8000` for the local single-operator MVP deployment target (SAD §5). Added
  `frontend/.env.example` documenting this variable; developers copy it to `.env.local` (already
  git-ignored by the existing `frontend/.gitignore` `.env*` rule).
- **`src/app/page.tsx`** — updated to the real `pollRun(run_id)` signature (the stub's `requisition`/
  `elapsedMs` parameters existed only to fake elapsed time client-side and are gone now that the backend
  tracks real run state); added `try/catch` around both `submitRun` and each `pollRun` tick so a thrown
  `RunClientError` (validation, pipeline, or network failure) renders as a `failed`-status assistant message
  instead of an unhandled rejection. Removed the now-unused `useRef`-based elapsed-time tracking.
- No changes to `RequisitionForm.tsx`, `ChatMessage.tsx`, or `types.ts` — the existing component contracts
  and mirrored types already matched the real backend, confirming `@frontend.eng`'s stub was faithful to
  the SAD contract.

### Backend changes

None required. CORS was already open (`allow_origins=["*"]`) per `backend/app/main.py`, sufficient for the
frontend's `http://localhost:3000` origin at MVP scope — confirmed via a live `OPTIONS` preflight check
(see Verification Performed), not just read from the code.

## Verification Performed (`*verify-messageflow`)

Both processes were run live, not just inspected as code:

1. **Backend standalone**: `uvicorn app.main:app` on port 8000 (Python 3.13 venv per `backend.md`'s pinned
   version). `GET /health` → `200 {"status": "ok"}`.
2. **Direct API round trip** (`curl`, no frontend involved): `POST /api/runs` with a minimal valid
   requisition → `202 {run_id, status: "pending"}`; polled `GET /api/runs/{run_id}` and observed the real
   lifecycle `pending → running → failed` within ~2s, with
   `error: {"code": "pipeline_error", "message": "Error code: 401 - ... Incorrect API key provided:
   your_ope***here ..."}` — the placeholder `OPENAI_API_KEY` in this environment's `.env` causes a genuine
   OpenAI `401`, propagated end-to-end through CrewAI → `run_crew()` → the API's exception handler → the
   error envelope. This is the same partially-successful smoke test `@backend.eng` ran solo in `backend.md`;
   confirmed reproducible from the integration layer's perspective too.
3. **CORS preflight**: `OPTIONS /api/runs` with `Origin: http://localhost:3000` → `200`,
   `access-control-allow-origin: *`, confirming the frontend's browser-side `fetch` calls won't be blocked.
4. **Full browser round trip**: `next dev` on port 3000 with `NEXT_PUBLIC_API_URL=http://localhost:8000` in
   `.env.local`; drove the actual rendered page with a headless-Chromium Playwright script (no
   `chromium-cli`/browser tool available in this session, so a one-off Playwright driver was installed to
   `/tmp` and used instead — not committed to the repo). Filled in the job title and description, clicked
   "Start run", and observed in the rendered DOM: the user's requisition bubble, a loading bubble, then a
   red error bubble reading **"Run failed (pipeline_error)"** with the same OpenAI `401` message from step 2
   — i.e., the real network round trip from the browser's `fetch`, through the FastAPI backend, into the
   CrewAI pipeline, and back out through the polling loop into the rendered UI. `console --errors` equivalent
   (`page.on("console"/"pageerror")`) captured zero JS errors. Screenshot evidence retained at
   `/tmp/screenshots/03-failed.png` (not committed — ephemeral verification artifact, same treatment as the
   Trace Log files `@backend.eng` deleted after their own smoke test).
5. **Static checks**: `npx eslint .` (frontend) — 0 errors, 0 warnings. `npm run build` (Next.js production
   build) — compiles successfully, type-checks cleanly against `runClient.ts`'s new `RunClientError` type
   and `page.tsx`'s updated call sites.

**Not verified** (unchanged gap from `backend.md`, now also blocking full integration verification): a
real, fully-**successful** run (`pending → running → succeeded` with an actual LLM/search-generated report
rendered in the chat) — this environment has only placeholder `OPENAI_API_KEY`/`SERPER_API_KEY` values, so
the pipeline cannot reach `succeeded` for real. The `succeeded`-path UI code (markdown report rendering via
`react-markdown`) is unchanged from `@frontend.eng`'s original stub, which already exercised that render
path against a canned two-section report — so the rendering logic itself is exercised, just not with a real
end-to-end success. This is the same "smoke/acceptance criterion only partially satisfied" gap `backend.md`
already flagged; integration doesn't resolve it, since it requires real API keys the operator hasn't
supplied yet.

## Known Issues / Gaps

- **No real success-path end-to-end run** (see above) — requires valid `OPENAI_API_KEY` and
  `SERPER_API_KEY` in `.env`; re-run this integration's step 4 once those are supplied.
- **No automated test for the wiring itself**: `backend/tests/` covers the API in isolation (mocked
  `run_crew`) and there is no frontend test suite (`frontend/` has no test runner configured) — this
  integration was verified manually (see above), not via a committed regression test. A future
  `@qa.eng` pass (SAD §9 "Smoke/acceptance") should add an automated integration test (e.g. Playwright
  against both processes) rather than relying on manual verification each time.
- **CORS remains wide open** (`allow_origins=["*"]`) — acceptable at MVP per SAD §8 ("none for MVP... if
  ever exposed beyond localhost"), unchanged by this integration; flagged again here since this is the
  layer that would need to tighten it if the frontend/backend origins diverge from localhost.
- **No request timeout / retry on the frontend `fetch` calls** — if the backend hangs mid-run beyond what
  the operator is willing to wait, the polling loop (`page.tsx`) will keep polling indefinitely with no
  cancel action exposed in the UI. Not a PRD requirement (no mid-pipeline approval gate, PRD §6) but worth
  flagging for `@qa.eng`/future UX work.
- **`NEXT_PUBLIC_API_URL` must be known at `next dev`/`next build` time** (Next.js bakes
  `NEXT_PUBLIC_*` vars in at build time for the client bundle) — if `@devops.eng` deploys frontend and
  backend to different hosts later (SAD §5 currently assumes both are local/localhost), this needs to be
  set correctly in that environment's build step, not just its runtime env.
- **Playwright verification tooling is not part of the repo** — the browser driver used in step 4 above was
  installed ad hoc to `/tmp` for this session only, per this persona's scope (verify, don't necessarily
  productionize test infra). If `@qa.eng` wants repeatable browser-level regression tests, that's a
  deliberate, separate setup decision (e.g. add `@playwright/test` as a frontend devDependency), not
  something this integration pass silently added.

## Sources

- `project-context/1.define/prd.md`
- `project-context/1.define/sad.md`
- `project-context/2.build/frontend.md`
- `project-context/2.build/backend.md`
- `.cursor/agents/integration-eng.md`
- Live verification: `backend/app/main.py`, `backend/app/models.py`, `frontend/src/lib/runClient.ts`,
  `frontend/src/app/page.tsx` (this session)

## Assumptions

- `project-context/2.build/setup.md`'s absence is not blocking, matching the precedent both `@frontend.eng`
  and `@backend.eng` already recorded — the PRD/SAD/Build docs fully specify the contract needed to wire the
  two sides.
- `NEXT_PUBLIC_API_URL=http://localhost:8000` is the correct MVP default, matching SAD §5's "single-instance
  local... process" target; not yet a concern for a non-local deployment (Open Question below).
- The ad hoc `/tmp`-installed Playwright driver used for verification is treated as a throwaway diagnostic
  tool for this session, not a project deliverable — nothing under `frontend/` or `backend/` depends on it.

## Open Questions

- **Real success-path verification**: carried forward from `backend.md` — needs valid `OPENAI_API_KEY`/
  `SERPER_API_KEY` from the operator before anyone can confirm the `succeeded` status and real report
  rendering actually work end-to-end, not just the `failed` path exercised here.
- **Synchronous vs. async API pattern** (carried from SAD/backend.md): still unresolved; unaffected by this
  integration either way since the frontend's poll loop works against either.
- **Multi-host deployment**: if frontend and backend are ever deployed to separate hosts/ports beyond this
  session's localhost setup, `NEXT_PUBLIC_API_URL` and the backend's CORS `allow_origins` both need explicit,
  coordinated configuration — not addressed here since SAD's MVP scope is single-instance/local only.
- **Automated regression coverage for the integration layer itself**: should `@qa.eng` add a committed
  Playwright (or similar) test, or is manual verification per integration change acceptable at this
  project's single-operator MVP scale?

## Audit

- **Timestamp**: 2026-08-20
- **Persona**: `integration-eng`
- **Action**: `integrate-api` (`verify-messageflow`, `log-integration`)
- **Resolved AAMAD_TARGET_RUNTIME**: AAMAD_TARGET_RUNTIME=crewai (from `aamad.config.yml`; integration layer is runtime-agnostic at the HTTP contract)
- **Upstream artifacts**: `project-context/1.define/prd.md`, `project-context/1.define/sad.md`,
  `project-context/2.build/frontend.md`, `project-context/2.build/backend.md`
- **Files changed**: `frontend/src/lib/runClient.ts` (rewritten from stub), `frontend/src/app/page.tsx`
  (updated call sites + error handling), `frontend/.env.example` (added).
- **Test results**: `npx eslint .` clean; `npm run build` succeeds; live backend `curl` round trip
  (`pending → running → failed`, correct error envelope); live CORS preflight `200`; live browser round trip
  via ad hoc Playwright driver (`pending/running → failed`, 0 console errors), screenshot retained locally
  (not committed).
