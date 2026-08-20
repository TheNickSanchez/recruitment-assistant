"use client";

import { FormEvent, useState } from "react";
import type { JobRequisition } from "@/lib/types";

interface RequisitionFormProps {
  disabled: boolean;
  onSubmit: (requisition: JobRequisition) => void;
}

// Mirrors backend/app/models.py's JobRequisition.candidate_count Field(ge=1, le=25).
const MIN_CANDIDATES = 1;
const MAX_CANDIDATES = 25;

function clampCandidateCount(value: number): number {
  if (Number.isNaN(value)) return MIN_CANDIDATES;
  return Math.min(MAX_CANDIDATES, Math.max(MIN_CANDIDATES, Math.round(value)));
}

const EMPTY: JobRequisition = {
  title: "",
  description: "",
  responsibilities: "",
  requirements: "",
  preferred_qualifications: "",
  perks: "",
  candidate_count: 10,
};

export function RequisitionForm({ disabled, onSubmit }: RequisitionFormProps) {
  const [requisition, setRequisition] = useState<JobRequisition>(EMPTY);
  const [expanded, setExpanded] = useState(false);

  const canSubmit = requisition.title.trim().length > 0 && requisition.description.trim().length > 0;

  function update<K extends keyof JobRequisition>(key: K, value: JobRequisition[K]) {
    setRequisition((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit || disabled) return;
    onSubmit({ ...requisition, candidate_count: clampCandidateCount(requisition.candidate_count) });
    setRequisition(EMPTY);
    setExpanded(false);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          className="flex-1 rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
          placeholder="Job title (e.g. Senior Backend Engineer)"
          value={requisition.title}
          onChange={(e) => update("title", e.target.value)}
          disabled={disabled}
          required
        />
        <input
          type="number"
          min={MIN_CANDIDATES}
          max={MAX_CANDIDATES}
          className="w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 sm:w-32 dark:border-zinc-700"
          value={requisition.candidate_count}
          onChange={(e) => update("candidate_count", clampCandidateCount(Number(e.target.value)))}
          disabled={disabled}
          title={`Candidate count (${MIN_CANDIDATES}-${MAX_CANDIDATES})`}
        />
      </div>

      <textarea
        className="min-h-20 resize-y rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
        placeholder="Job description — what is this role, and why does it exist?"
        value={requisition.description}
        onChange={(e) => update("description", e.target.value)}
        disabled={disabled}
        required
      />

      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="self-start text-xs font-medium text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
      >
        {expanded ? "Hide" : "Add"} responsibilities, requirements, qualifications & perks
      </button>

      {expanded && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <textarea
            className="min-h-16 resize-y rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
            placeholder="Responsibilities"
            value={requisition.responsibilities}
            onChange={(e) => update("responsibilities", e.target.value)}
            disabled={disabled}
          />
          <textarea
            className="min-h-16 resize-y rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
            placeholder="Requirements"
            value={requisition.requirements}
            onChange={(e) => update("requirements", e.target.value)}
            disabled={disabled}
          />
          <textarea
            className="min-h-16 resize-y rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
            placeholder="Preferred qualifications"
            value={requisition.preferred_qualifications}
            onChange={(e) => update("preferred_qualifications", e.target.value)}
            disabled={disabled}
          />
          <textarea
            className="min-h-16 resize-y rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-zinc-500 dark:border-zinc-700"
            placeholder="Perks"
            value={requisition.perks}
            onChange={(e) => update("perks", e.target.value)}
            disabled={disabled}
          />
        </div>
      )}

      <button
        type="submit"
        disabled={!canSubmit || disabled}
        className="self-end rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
      >
        {disabled ? "Run in progress…" : "Start run"}
      </button>
    </form>
  );
}
