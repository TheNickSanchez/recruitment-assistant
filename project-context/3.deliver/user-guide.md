# User Guide — Recruitment Assistant

**Persona**: @devops.eng | **Action**: `*document-user-guide` | **Status**: MVP

## 1. Product Overview

Recruitment Assistant is a personal, single-operator tool: you paste one job requisition into a chat-style page and a three-agent CrewAI pipeline researches public-web candidates, scores them against the role, and returns one markdown report with recommendations and draft outreach. Nothing is sent to candidates.

It is for the project owner acting as recruiter or hiring manager on their own open role. It is not a multi-user product and does not store runs after the backend process stops.

**MVP limitations**: no LinkedIn login/scraping; outreach is draft-only; no run history; no login; a live successful report needs valid OpenAI and Serper keys loaded into the backend process. QA verified the submit → poll → **error** path end-to-end; the live **success** path was blocked by placeholder/missing keys. See `project-context/2.build/qa.md` and `project-context/3.deliver/deploy.md`.

## 2. Prerequisites

- **OS**: macOS, Linux, or Windows with Python 3.13 and Node.js 20+ (or Docker Compose instead of local runtimes).
- **Accounts / keys** (values stay in your local `.env`, never in git):
  - `OPENAI_API_KEY` (required for a real run)
  - `SERPER_API_KEY` (required for web search tools)
  - optional `OPENAI_MODEL` (example default `gpt-4o`)
- **Browser**: a current desktop browser (Chrome, Firefox, Safari, Edge). No dedicated mobile app.
- **Config**: `aamad.config.yml` already sets `runtime.target: crewai`; you do not need to change it for normal use.

## 3. Installation

Detailed operator steps (including Docker and rollback) live in [`deploy.md`](deploy.md). Short path:

1. Copy `.env.example` to `.env` at the repo root and fill `OPENAI_API_KEY` and `SERPER_API_KEY`.
2. **Backend** (from `backend/`): create a Python 3.13 venv, `pip install -r requirements.txt`, then  
   `uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ../.env`  
   The app does not auto-load `.env`; `--env-file` (or Docker `env_file`) is required.
3. **Frontend** (from `frontend/`): copy `.env.example` to `.env.local`, `npm install`, `npm run dev`.
4. **Verify**: `curl http://127.0.0.1:8000/health` should return `{"status":"ok"}`. Open `http://127.0.0.1:3000`.

Alternatively: `cp .env.example .env` (fill keys) then `docker compose up --build`.

There is no `setup.md` for this project; this guide follows the implemented `backend/` + `frontend/` layout.

## 4. Getting Started

1. Open the chat UI (local port 3000).
2. Enter at least a **job title** and **description**. Optional: responsibilities, requirements, preferred qualifications, perks, and candidate count (1–25, default 10).
3. Click **Start run**. You should see your requisition in the thread and a loading state (“Queuing run…” then research/scoring copy) while the UI polls the API.
4. Wait on the order of **minutes** for a live run (three sequential LLM + search stages). There is no mid-pipeline approval step.
5. On success, the assistant bubble renders markdown with **Recommendations** and **Outreach Guidance**. Treat outreach text as drafts only.
6. On failure, the chat shows `Run failed (<code>)` plus the backend message (for example `pipeline_error` if the LLM/search call failed). That is expected if keys are missing.

The sidebar “Coming later” items (run history, LinkedIn sourcing, send outreach, batch runs) are disabled placeholders, not features.

## 5. Everyday Use

- **One requisition per run.** Submit, wait, read the report, act outside the tool (email, ATS, etc.).
- **Candidate count** caps search/LLM cost; keep it near the default 10 unless you accept more API usage.
- **In-session history**: you can start another run in the same page; runs are not saved across backend restarts.
- **How to read the report**: scores and justifications are model-generated from public web search/scrape — verify facts and contact paths before outreach. Do not treat the list as complete or legally reviewed.
- **Errors**: `validation_error` means the form/API rejected input; `pipeline_error` means the crew failed after submit; `network_error` means the UI could not reach the API.

## 6. Troubleshooting

| What you see | What to try |
|---|---|
| Start run stays disabled | Fill title and description. After a failed run the form may have cleared — re-enter fields. |
| `pipeline_error` / OpenAI connection or 401 | Put real keys in `.env` and restart uvicorn with `--env-file ../.env` (or restart Compose). |
| `network_error` / Failed to fetch | Start the backend; confirm `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). |
| Run gone after refresh/restart | Expected — state is in memory only. |
| Page keeps polling | No cancel control in MVP; stop the backend or reload. |
| Telemetry SSL noise in backend logs | Ensure `CREWAI_TELEMETRY_OPT_OUT=true` is in the **process** environment. |

**Logs**: stdout (`docker compose logs` or the uvicorn terminal), rotating `project-context/2.build/logs/app.log`, and per-run JSONL `project-context/2.build/logs/{run_id}.jsonl`. Optional CrewAI AMP traces: see [`deploy.md`](deploy.md) Monitoring & Observability (`crewai login`, `CREWAI_TRACING_ENABLED=true`).

More cases: [`deploy.md`](deploy.md) Troubleshooting.

## 7. Deployment Notes (operators)

Use [`deploy.md`](deploy.md) as the runbook: local vs Docker, env-var matrix (names only), CI (lint/test/build only), access-control warnings (no auth — keep on localhost), and rollback (`git checkout` previous revision and restart; no database to restore). Remote/cloud deploy is not part of this MVP unless you explicitly authorize it.

## Sources

- `project-context/1.define/prd.md`
- `project-context/2.build/integration.md`
- `project-context/2.build/qa.md`
- `project-context/3.deliver/deploy.md`
- `.cursor/templates/user-guide-template.md`
- `aamad.config.yml` (`documentation.require_user_guide: true`)
- `setup.md`: not present
- `security.md`: not present (accepted Tier-0 gap; see deploy.md)

## Assumptions

- Operator uses localhost or Docker on their machine.
- Real API keys are supplied by the operator; this guide does not include a live success screenshot.
- Chat UI (not CLI) is the supported interface, matching the implemented frontend.

## Open Questions

- Same as deploy.md: live success-path confirmation once keys are present; whether in-app `.env` loading should be added later.

## Audit

- **Timestamp**: 2026-08-24
- **Persona**: `devops-eng`
- **Action**: `document-user-guide` (log-path sync after observability work)
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai`
- **Prompt Trace**: omitted — documentation artifact, not a production LLM task.
