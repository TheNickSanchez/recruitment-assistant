# Deployment Runbook — Recruitment Assistant

**Persona**: @devops.eng | **Actions**: `*prepare-release`, `*define-deploy`, `*configure-cicd`, `*document-deploy` | **Status**: Config and runbook complete; no live cloud deploy authorized

**Release**: `0.1.0` (MVP) | **Runtime**: `crewai` | **Date**: 2026-08-24

## Release scope / version summary (`*prepare-release`)

**Version**: `0.1.0` — first packaged MVP of the personal Recruitment Assistant.

**In scope for this release**:

- Sequential 3-agent CrewAI pipeline (`researcher` → `evaluator` → `recommender`) behind FastAPI (`POST /api/runs`, `GET /api/runs/{run_id}`, `GET /health`).
- Next.js chat UI for one-requisition-in, one-markdown-report-out (PRD FR-1…FR-4).
- Local process start **or** Docker Compose (backend `:8000` + frontend `:3000`).
- CI that lints, tests, and builds — no automatic promotion.

**Out of scope** (PRD §4 P2 / SAD §5): authenticated LinkedIn sourcing, outreach send, persistent storage, multi-user/IAM, IaC, multi-region, dedicated observability stack, live cloud hosting.

**Runtime alignment**: packaging uses Python 3.13 + CrewAI + FastAPI (`AAMAD_TARGET_RUNTIME=crewai`). Agent/task YAML remains at `backend/app/config/agents.yaml` and `backend/app/config/tasks.yaml`. Existing entrypoints are reused: `backend/app/main.py` (FastAPI) and `backend/requirements.txt`. No duplicate root `main.py` / `requirements.txt` was added.

### QA gate

`project-context/2.build/qa.md` exists. **Verdict: conditional pass** with explicitly scoped known gaps — this satisfies the Deliver phase gate (pass **or** scoped gaps).

| Area | Result |
|---|---|
| Backend pytest | 15/15 pass (YAML/crew guards + mocked API lifecycle) |
| Frontend lint / `tsc` | Clean |
| Live FR-1 submit → poll → error surfacing | Pass (API and chat UI) |
| Live FR-2…FR-4 **success** path (`pending → running → succeeded` + real report) | **Not met** — placeholder/missing API keys (QA DEF-2); FastAPI does not auto-load repo-root `.env` (QA DEF-1) |

Proceeding to Deliver with those gaps documented below. A live success-path run still requires operator-supplied `OPENAI_API_KEY` and `SERPER_API_KEY` loaded into the backend process (Compose `env_file` or `uvicorn --env-file ../.env`).

### Security.md status

`project-context/2.build/security.md` is **not present**. `aamad.config.yml` sets `security.require_security_assessment: true`, and PRD §5 / SAD §8 require `@security.eng` before Deliver.

**Disposition for this release**: accepted gap for this **Tier-0 mini-project**, per operator instruction on this Deliver pass. Recorded under Assumptions. `@security.eng` remains recommended before any exposure beyond localhost.

No Diagnostic halt: QA artifact is present with a scoped verdict, and the operator accepted the missing security assessment.

## Hosting approach (`*define-deploy`)

SAD §5: smallest MVP-appropriate target — a single-instance local or lightly-hosted Python (FastAPI/uvicorn) process, plus the Next.js chat UI. No cloud provisioner is configured. This runbook does **not** deploy to a remote environment.

| Mode | When to use | Processes / ports | Health |
|---|---|---|---|
| **Local (default)** | Day-to-day personal use | uvicorn `127.0.0.1:8000`; Next.js `127.0.0.1:3000` | `GET http://127.0.0.1:8000/health` → `{"status":"ok"}` |
| **Docker Compose** | Repeatable containerized local run | `backend` `:8000`, `frontend` `:3000` | Compose healthcheck hits the same `/health` endpoint |

**Images**:

- Repo-root `Dockerfile` — Python 3.13-slim, `pip install -r backend/requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `frontend/Dockerfile` — Node 20, `npm ci` / `npm run build` / `next start`. `NEXT_PUBLIC_API_URL` is a **build-arg** (default `http://localhost:8000`) because Next.js inlines `NEXT_PUBLIC_*` into the client bundle. The browser calls the API, so this must be the **host-reachable** URL, not the Compose service name `backend`.

**Start command alignment (crewai adapter)**: container CMD is uvicorn over the existing FastAPI app that calls `RecruitmentCrew().crew().kickoff(...)`. Crew YAML and `Process.sequential` / `memory=False` are unchanged.

## Environment variable matrix

Names only — copy `.env.example` → `.env` (repo root) and `frontend/.env.example` → `frontend/.env.local` for local Next.js. Never commit values (`security.forbid_committed_secrets: true`).

| Variable | Where defined | Required | Used by | Notes |
|---|---|---|---|---|
| `OPENAI_API_KEY` | repo-root `.env.example` | **Yes** (live runs) | CrewAI / LiteLLM | Without a real key the pipeline fails with `pipeline_error` (QA DEF-2). |
| `OPENAI_MODEL` | repo-root `.env.example` | No | CrewAI default LLM | Example default `gpt-4o`. Provider/model is still a PRD Open Question; this repo inherited OpenAI env names. |
| `SERPER_API_KEY` | repo-root `.env.example` | **Yes** (live runs) | `SerperDevTool` | Required for researcher/evaluator/recommender web search. |
| `CREWAI_TELEMETRY_OPT_OUT` | repo-root `.env.example` | Recommended `true` | CrewAI anonymous telemetry | Distinct from AMP **tracing**. QA DEF-4: telemetry still attempted if the process never received the var (same as DEF-1). |
| `CREWAI_TRACING_ENABLED` | repo-root `.env.example` | No (default `false`) | `RecruitmentCrew` (`tracing=True` when set) | Opt-in CrewAI AMP traces. Requires `crewai login`. Sends prompts/tool I/O (candidate data) to CrewAI AMP. |
| `LOG_LEVEL` | repo-root `.env.example` | No (default `INFO`) | stdlib logging | `DEBUG` / `INFO` / `WARNING` / `ERROR`. Health and run-status polls are `DEBUG`. |
| `LOG_TO_FILE` | repo-root `.env.example` | No (default `true`) | stdlib logging | Rotating `project-context/2.build/logs/app.log` (2 MB × 3 backups). Stdout always. |
| `AAMAD_TARGET_RUNTIME` | repo-root `.env.example` | No (docs/config) | AAMAD / operator | `crewai`. Application runtime does not switch on this at request time. |
| `APP_NAME` | repo-root `.env.example` | No | Startup log | Included in the INFO startup line. |
| `APP_ENV` | repo-root `.env.example` | No | Startup log | Included in the INFO startup line (default `development`). |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.example` | No (has default) | Next.js browser client | Default `http://localhost:8000`. Must be set at **frontend build** time for Docker/production `next start`. |

**How the backend gets keys (QA DEF-1)**: `python-dotenv` is listed in `backend/requirements.txt` but `load_dotenv` is **not** called in application code. This persona does not change application logic. Operators must inject env into the process:

- Local: `uvicorn ... --env-file ../.env` from `backend/` (or export vars in the shell).
- Docker: `env_file: .env` in `docker-compose.yml`.

## How to install, start, stop, and roll back

### Prerequisites

- Python **3.13** (pinned in `.python-version` and the backend image; 3.14 wheels were not available at Build time).
- Node.js **20+** (local frontend) or Docker Engine + Compose v2.
- Operator-provided `OPENAI_API_KEY` and `SERPER_API_KEY`.

### Local install and start

```bash
# 1. Secrets (repo root)
cp .env.example .env
# Edit .env — put real keys in OPENAI_API_KEY and SERPER_API_KEY. Do not commit .env.

# 2. Backend
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ../.env
```

In a second terminal:

```bash
cd frontend
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                  # http://127.0.0.1:3000
```

Smoke: `curl -s http://127.0.0.1:8000/health` → `{"status":"ok"}`. Open the chat UI, submit title + description. With valid keys, poll until `succeeded` and a two-section markdown report. Without keys, chat should show `Run failed (pipeline_error)` rather than fail silently.

Stop: Ctrl+C both processes. In-memory run state is discarded (SAD §4).

### Docker Compose install and start

```bash
cp .env.example .env   # fill real keys
docker compose up --build
```

UI: `http://127.0.0.1:3000`. API: `http://127.0.0.1:8000`. Logs: `docker compose logs -f backend frontend`. Trace JSONL: `project-context/2.build/logs/` (bind-mounted).

Stop: `docker compose down`. Wipe images/containers from this project only: `docker compose down --rmi local`.

### Rollback

There is no hosted environment or migration. Rollback is **revert the tree and restart**:

1. Stop local processes or `docker compose down`.
2. `git checkout <previous-tag-or-commit>` (or `git revert` on a shared branch). Suggested tag when one is cut: `v0.1.0`.
3. Reinstall only if dependencies changed (`pip install -r backend/requirements.txt`, `npm ci` in `frontend/`).
4. Start again with the same `--env-file` / Compose `env_file` contract.

Because run state is in-process only, restart always drops in-flight and completed runs — there is no data rollback. API keys stay in `.env` (untracked).

**Promotion**: CI does not deploy. Any future host is a **manual** copy of this Compose/local procedure after CI is green. No live deploy was executed for this release.

## Access control (MVP scope)

- **Chat/API AuthN/AuthZ**: none (PRD §3, SAD §8). Single local operator assumed.
- **Network**: prefer binding local processes to `127.0.0.1`. Compose publishes `3000` and `8000` on the host; do **not** put this stack on a public interface without adding auth (SAD Open Question).
- **CORS**: backend `allow_origins=["*"]` — acceptable for localhost MVP; tighten if origins are no longer local.
- **Secrets**: LLM and Serper keys are operator-provided env vars only. Least privilege: those keys are for this personal tool; do not reuse production org credentials if a narrower key exists. No deployment-platform credentials are used in this MVP.
- **Candidate data**: not stored server-side; it still transits OpenAI and Serper during a run. Provider terms are an unresolved PRD Open Question.
- **Enterprise IAM / SSO / network segmentation**: Future Work.

## Monitoring & Observability

SAD §5 still defers a dedicated APM stack. This release adds **basic process logging** plus **optional CrewAI AMP tracing**.

### What to monitor

| Signal | Why it matters | How to watch |
|---|---|---|
| Process up | Operator can submit runs | `GET /health` → `{"status":"ok"}`; Compose healthcheck |
| API 4xx/5xx | Bad input vs backend faults | `WARNING`/`ERROR` lines `request method=… status=…` in app logs |
| Run lifecycle | FR-1 submit → execute → finish | `run submitted` / `crew run started` / `crew kickoff starting` / `crew task finished` / `crew run succeeded` or `crew run failed` |
| Pipeline failures | Missing keys, LLM/search errors | `ERROR` with stack (`crew run failed`, `crew kickoff failed`); JSONL `run_failed` |
| Cost / duration | Sequential LLM + search; minutes per run | Wall-clock from kickoff→completed logs; CrewAI AMP token/cost metrics if tracing is on |
| CrewAI AMP traces (opt-in) | Agent reasoning, tools, LLM prompts | [app.crewai.com](https://app.crewai.com) Traces tab |

Do **not** treat `/health` as “pipeline healthy” — it only means the FastAPI process is up.

High-frequency `GET /health` and `GET /api/runs/{run_id}` polls are logged at **DEBUG** so INFO stays readable.

### Log levels and where logs are stored

| Level | Typical events |
|---|---|
| `DEBUG` | Health checks; successful status polls |
| `INFO` | Startup/shutdown; `POST /api/runs`; crew kickoff/task/complete |
| `WARNING` | 4xx (validation `422`, unknown run `404`) |
| `ERROR` | 5xx; unhandled request exceptions; crew/pipeline exceptions (`logger.exception`) |

| Store | Path / sink | Contents |
|---|---|---|
| Stdout | uvicorn terminal or `docker compose logs -f backend` | Same events; secret-redacted |
| App log file | `project-context/2.build/logs/app.log` | Rotating file (gitignored `*.log`); disable with `LOG_TO_FILE=false` |
| Per-run JSONL | `project-context/2.build/logs/{run_id}.jsonl` | `run_submitted` / `run_started` / `run_succeeded` / `run_failed` (secret-redacted). Gitignored `*.jsonl`. |
| Crew verbose | stdout (Crew `verbose=True`) | CrewAI’s own agent/task console output |
| Prompt Trace (local AAMAD adapter) | **Not implemented** | Local rendered-prompt capture is still a backend.md gap. Use CrewAI AMP tracing (below) if you need prompt/tool detail. |

Startup log includes `runtime=crewai`, `LOG_LEVEL`, and whether AMP tracing is enabled. Request logs include method, path, status, and duration_ms. Crew logs include `job_title` and `candidate_count` only — not the full requisition or report body.

### CrewAI tracing setup and access (optional)

AMP tracing is **off by default** (`CREWAI_TRACING_ENABLED=false`) because traces include prompts and tool I/O (candidate-identifying content). `tracing=True` is passed on `RecruitmentCrew` when the operator opts in.

1. Create a free account at [app.crewai.com](https://app.crewai.com).
2. From the backend venv (CLI lives in the `crewai` package):

   ```bash
   cd backend
   source .venv/bin/activate
   crewai login
   ```

   The CLI opens a browser, asks for a device code, and authenticates this machine to CrewAI AMP.

3. Set in repo-root `.env` (loaded via `--env-file` / Compose `env_file`):

   ```
   CREWAI_TRACING_ENABLED=true
   ```

   Restart uvicorn or Compose so `RecruitmentCrew` is constructed with `tracing=True`.

   Global alternative (same effect for Crews that do not pass `tracing=False`): `export CREWAI_TRACING_ENABLED=true` or `crewai traces enable`. This project’s explicit `tracing=` flag follows the env flag so the runbook and code stay aligned.

4. Run a requisition through the chat UI (or `POST /api/runs`).
5. View traces: log in at [app.crewai.com](https://app.crewai.com) → **Traces** tab, or open [trace batches](https://app.crewai.com/crewai_plus/trace_batches). You should see agent decisions, task timeline, tool calls, LLM calls, timing, and errors.

`CREWAI_TELEMETRY_OPT_OUT=true` only suppresses anonymous telemetry (`telemetry.crewai.com`). It does **not** replace AMP tracing. If traces do not appear: confirm `crewai login`, `CREWAI_TRACING_ENABLED=true` in the **process** environment, a real crew execution (not the pytest stub), and network access to CrewAI AMP.

No APM, metrics backend, or alerting in MVP (SAD §5). Crew-level cost control remains `max_rpm=20` and bounded `candidate_count` (default 10, max 25).

## Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `pipeline_error` / OpenAI connection or 401 | Missing or placeholder `OPENAI_API_KEY`; process did not load `.env` (QA DEF-1/DEF-2) | Confirm `.env` has real keys. Restart with `--env-file ../.env` or Compose `env_file`. |
| Serper / search tool failures | Missing `SERPER_API_KEY` | Set the key in `.env` and restart the backend. |
| Chat `network_error` / Failed to fetch | Backend down or `NEXT_PUBLIC_API_URL` wrong | Start uvicorn; for Docker rebuild frontend if the API URL changed (build-time var). |
| `422` on submit | Missing title/description or `candidate_count` outside 1–25 | Fill required fields; keep candidate count in range. |
| CORS errors in the browser | Unexpected origin vs open CORS | MVP allows `*`; if you reversed that locally, allow `http://localhost:3000`. |
| CrewAI telemetry SSL noise | Opt-out not in process env (QA DEF-4) | Set `CREWAI_TELEMETRY_OPT_OUT=true` on the uvicorn/Compose process. |
| Run “disappeared” after restart | In-memory `run_store` | Expected. Re-submit the requisition. |
| Polling never ends | No cancel/timeout in UI (qa.md known limitation) | Stop the backend or refresh the page; there is no cancel API. |
| Docker frontend cannot reach API | `NEXT_PUBLIC_API_URL` set to `http://backend:8000` | Use `http://localhost:8000` (browser-side). Rebuild frontend. |
| Python 3.14 install fails | Unsupported wheels | Use 3.13 (`.python-version` / backend image). |
| CrewAI AMP traces missing | Not logged in; tracing env not on the process; pytest stub | `crewai login`; `CREWAI_TRACING_ENABLED=true` + restart; run a real crew, then check [Traces](https://app.crewai.com/crewai_plus/trace_batches). |
| Healthcheck slow to pass | CrewAI import at uvicorn startup | Compose `start_period` is 90s; wait and `docker compose logs backend`. |

## CI scaffolding (`*configure-cicd`)

`.github/workflows/ci.yml` runs on push/PR:

1. **Backend**: Python 3.13, `pip install -r backend/requirements.txt`, `pytest -v` (mocked crew; no live LLM/search).
2. **Frontend**: Node 20, `npm ci`, `npm run lint`, `npm run build`.

No deploy job. Do not treat a green CI as a live-success-path certification (that still needs real keys).

## Future work (ops, not this release)

- Dedicated APM, alerting, autoscaling, multi-region, IaC.
- AuthN/AuthZ and CORS allowlist if exposed beyond localhost.
- `@security.eng` assessment (`security.md`) before any non-localhost host.
- In-app `load_dotenv` (backend change, not this persona) **or** keep `--env-file` as the documented contract.
- Local AAMAD Prompt Trace files; FE↔API Playwright in CI; live success-path smoke with real keys.
- Frontend poll timeout / cancel.

## Sources

- `project-context/1.define/prd.md` (FR-1…FR-4, infra, secrets, Phase 3)
- `project-context/1.define/sad.md` (§4 API, §5 DevOps, §8 Security)
- `project-context/2.build/qa.md` (conditional pass, DEF-1…DEF-5)
- `project-context/2.build/backend.md`
- `project-context/2.build/frontend.md`
- `project-context/2.build/integration.md`
- `aamad.config.yml` (`runtime.target: crewai`, security/docs/testing gates)
- `.env.example`, `frontend/.env.example`
- `.cursor/rules/adapter-crewai.mdc`, `.cursor/rules/delivery-workflow.mdc`
- `.cursor/agents/devops-eng.md`
- Implemented layout: `backend/app/main.py`, `backend/app/logging_config.py`, `backend/app/crew.py`, `backend/requirements.txt`, `backend/app/config/*.yaml`, `frontend/`
- CrewAI tracing docs: https://docs.crewai.com/en/observability/tracing

## Assumptions

- Operator accepted a missing `security.md` for this Tier-0 mini-project; Deliver continues with that gap recorded rather than a halt.
- Hosting target is localhost or Docker on the operator’s machine. Ports **8000** (API) and **3000** (UI). Health: `GET /health`.
- `AAMAD_TARGET_RUNTIME=crewai` (operator + `aamad.config.yml`); no adapter conflict.
- Existing `backend/app/main.py` and `backend/requirements.txt` are the canonical runtime files; Docker/CI consume them rather than duplicating at repo root.
- Env injection via uvicorn `--env-file` / Compose `env_file` is the intended DEF-1 mitigation without changing application logic.
- LLM provider remains OpenAI-shaped env vars as inherited; not newly decided here.
- Compose frontend talks to the API at `http://localhost:8000` from the **browser**.
- No live cloud deploy was requested; config + runbook only.
- Missing `setup.md` is not blocking (same as Build personas).
- CrewAI AMP tracing stays opt-in (`CREWAI_TRACING_ENABLED` default false) so candidate-bearing prompts are not sent to CrewAI AMP unless the operator authenticates and enables it.

## Open Questions

- Will the operator supply real `OPENAI_API_KEY` and `SERPER_API_KEY` and confirm a live `succeeded` report before treating this MVP as operationally complete?
- Should `@backend.eng` add `load_dotenv` for repo-root `.env`, or is `--env-file` / Compose `env_file` the lasting contract?
- Cut a git tag `v0.1.0` for rollback, or keep commit SHAs only?
- When (if ever) will `@security.eng` produce `security.md` before non-localhost use?
- Confirm LLM/search providers (carried from PRD/SAD).
- Deployment status: **not deployed remotely**. Authorize a host explicitly if that should change.

## Audit

- **Timestamp**: 2026-08-24
- **Persona**: `devops-eng`
- **Actions**: `prepare-release`, `define-deploy`, `configure-cicd`, `document-deploy`
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai` (operator `AAMAD_TARGET_RUNTIME=crewai`; matches `aamad.config.yml` `runtime.target`; no conflicting override)
- **Packaging**: `Dockerfile` (Python 3.13, uvicorn `app.main:app`), `frontend/Dockerfile` (Node 20), `docker-compose.yml`, `.github/workflows/ci.yml`, `.python-version`
- **Runtime start command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (image) / `--host 127.0.0.1 --port 8000 --env-file ../.env` (local)
- **LLM / model**: not pinned by this persona — `OPENAI_API_KEY` / `OPENAI_MODEL` at process env; CrewAI default wiring (LiteLLM). Temperature / max_tokens not set in deploy config.
- **Prompt Trace**: omitted — this artifact is a runbook/packaging record, not a CrewAI production task; application Prompt Trace is also unimplemented (backend.md).
- **Live deploy**: not executed (not authorized).
- **Application logic**: not modified.
- **Upstream artifacts**: `prd.md`, `sad.md`, `qa.md`, `backend.md`, `frontend.md`, `integration.md`, `aamad.config.yml`
- **Tooling**: Cursor IDE agent; no CrewAI kickoff for this persona.

### Audit (observability follow-up)

- **Timestamp**: 2026-08-24
- **Persona**: `devops-eng`
- **Action**: `document-deploy` (Monitoring & Observability) plus application logging (operator-requested; no agent/task logic change)
- **Resolved `AAMAD_TARGET_RUNTIME`**: `crewai`
- **Logging**: startup/shutdown; request middleware (method/path/status/duration); crew kickoff/task/complete; `logger.exception` on pipeline and unhandled request errors; rotating `app.log` + stdout; JSONL lifecycle unchanged
- **CrewAI tracing**: `Crew(..., tracing=env CREWAI_TRACING_ENABLED)` default false; documented `crewai login` and AMP dashboard
- **Prompt Trace (local)**: still omitted in-app; AMP traces optional
- **Live deploy**: not executed
- **Secrets**: env var names only; log redaction filter for API-key-like strings
