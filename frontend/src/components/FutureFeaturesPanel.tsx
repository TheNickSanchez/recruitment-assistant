// Visual stubs only (PRD §4 P2 / SAD §1 Future deferrals). Non-functional by
// design — @frontend.eng's *add-placeholders* action, not a hidden feature.

const STUBS = [
  {
    title: "Run history",
    detail: "Persist and revisit past requisitions & reports across sessions.",
  },
  {
    title: "Authenticated LinkedIn sourcing",
    detail: "Requires its own legal/security review before implementation.",
  },
  {
    title: "Send outreach",
    detail: "Currently draft-only — no message is ever sent to a candidate.",
  },
  {
    title: "Multi-requisition batch runs",
    detail: "Run several job requisitions in parallel.",
  },
];

export function FutureFeaturesPanel() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col gap-3 border-l border-zinc-200 p-4 lg:flex dark:border-zinc-800">
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Coming later</p>
      {STUBS.map((stub) => (
        <div
          key={stub.title}
          aria-disabled="true"
          className="cursor-not-allowed rounded-xl border border-dashed border-zinc-200 p-3 opacity-60 dark:border-zinc-800"
        >
          <p className="text-sm font-medium text-zinc-600 dark:text-zinc-300">{stub.title}</p>
          <p className="mt-1 text-xs text-zinc-400">{stub.detail}</p>
        </div>
      ))}
    </aside>
  );
}
