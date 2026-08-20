// Mirrors backend/app/models.py (SAD §4 API contract). Kept in sync manually —
// there is no shared schema package at MVP scope.

export type RunStatus = "pending" | "running" | "succeeded" | "failed";

export interface JobRequisition {
  title: string;
  description: string;
  responsibilities: string;
  requirements: string;
  preferred_qualifications: string;
  perks: string;
  candidate_count: number;
}

export interface RunErrorEnvelope {
  code: string;
  message: string;
}

export interface RunSubmissionResponse {
  run_id: string;
  status: RunStatus;
}

export interface RunResultResponse {
  run_id: string;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  report: string | null;
  error: RunErrorEnvelope | null;
}

export type ChatMessage =
  | { id: string; role: "user"; requisition: JobRequisition }
  | { id: string; role: "assistant"; status: RunStatus; report?: string; error?: RunErrorEnvelope };
