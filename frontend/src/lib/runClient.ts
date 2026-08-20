// Real client for the SAD §4 async submit/poll contract (POST /api/runs,
// GET /api/runs/{run_id}) against the FastAPI backend. Base URL is read from
// NEXT_PUBLIC_API_URL (see .env.example), defaulting to the local backend's
// uvicorn address for MVP single-operator use.

import type { JobRequisition, RunErrorEnvelope, RunResultResponse, RunSubmissionResponse } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class RunClientError extends Error {
  envelope: RunErrorEnvelope;

  constructor(envelope: RunErrorEnvelope) {
    super(envelope.message);
    this.envelope = envelope;
  }
}

async function parseErrorEnvelope(response: Response): Promise<RunErrorEnvelope> {
  try {
    const body = await response.json();
    // FastAPI's default 422 validation-error shape (SAD §4) is {"detail": [...]},
    // distinct from the custom {code, message} envelope used for run-failure states.
    if (body?.detail) {
      const detail = Array.isArray(body.detail) ? body.detail.map((d: { msg?: string }) => d.msg).join("; ") : String(body.detail);
      return { code: "validation_error", message: detail };
    }
  } catch {
    // response body wasn't JSON; fall through to the generic envelope below
  }
  return { code: "http_error", message: `${response.status} ${response.statusText}` };
}

export async function submitRun(requisition: JobRequisition): Promise<RunSubmissionResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requisition),
    });
  } catch (err) {
    throw new RunClientError({
      code: "network_error",
      message: err instanceof Error ? err.message : "Failed to reach the backend API.",
    });
  }

  if (!response.ok) {
    throw new RunClientError(await parseErrorEnvelope(response));
  }

  return response.json();
}

export async function pollRun(run_id: string): Promise<RunResultResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/runs/${run_id}`);
  } catch (err) {
    throw new RunClientError({
      code: "network_error",
      message: err instanceof Error ? err.message : "Failed to reach the backend API.",
    });
  }

  if (!response.ok) {
    throw new RunClientError(await parseErrorEnvelope(response));
  }

  return response.json();
}
