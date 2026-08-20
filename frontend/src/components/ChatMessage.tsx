import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatMessage as ChatMessageType } from "@/lib/types";

export function ChatMessage({ message }: { message: ChatMessageType }) {
  if (message.role === "user") {
    const { requisition } = message;
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-zinc-900 px-4 py-3 text-sm text-white dark:bg-zinc-100 dark:text-zinc-900">
          <p className="font-semibold">{requisition.title}</p>
          <p className="mt-1 whitespace-pre-wrap text-white/80 dark:text-zinc-900/70">
            {requisition.description}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-zinc-200 bg-white px-4 py-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        {message.status === "pending" || message.status === "running" ? (
          <LoadingBubble status={message.status} />
        ) : message.status === "failed" ? (
          <ErrorBubble error={message.error} />
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.report ?? ""}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

function LoadingBubble({ status }: { status: "pending" | "running" }) {
  return (
    <div className="flex items-center gap-2 text-zinc-500 dark:text-zinc-400">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-current" />
      </span>
      {status === "pending" ? "Queuing run…" : "Researching, scoring, and drafting outreach…"}
    </div>
  );
}

function ErrorBubble({ error }: { error?: { code: string; message: string } }) {
  return (
    <div className="text-red-600 dark:text-red-400">
      <p className="font-semibold">Run failed{error ? ` (${error.code})` : ""}</p>
      <p className="mt-1 text-red-500/90 dark:text-red-400/80">
        {error?.message ?? "Unknown error."}
      </p>
    </div>
  );
}
