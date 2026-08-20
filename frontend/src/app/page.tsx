"use client";

import { useState } from "react";
import { ChatMessage } from "@/components/ChatMessage";
import { FutureFeaturesPanel } from "@/components/FutureFeaturesPanel";
import { RequisitionForm } from "@/components/RequisitionForm";
import { pollRun, RunClientError, submitRun } from "@/lib/runClient";
import type { ChatMessage as ChatMessageType, JobRequisition } from "@/lib/types";

const POLL_INTERVAL_MS = 700;

export default function Home() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  function setAssistantFailed(assistantId: string, err: unknown) {
    const envelope =
      err instanceof RunClientError
        ? err.envelope
        : { code: "unknown_error", message: err instanceof Error ? err.message : "Unknown error." };
    setMessages((prev) =>
      prev.map((m) => (m.id === assistantId ? { id: m.id, role: "assistant", status: "failed", error: envelope } : m))
    );
    setIsRunning(false);
  }

  async function handleSubmit(requisition: JobRequisition) {
    const userMessage: ChatMessageType = {
      id: `user-${Date.now()}`,
      role: "user",
      requisition,
    };
    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: "assistant", status: "pending" },
    ]);
    setIsRunning(true);

    let run_id: string;
    try {
      ({ run_id } = await submitRun(requisition));
    } catch (err) {
      setAssistantFailed(assistantId, err);
      return;
    }

    const tick = async () => {
      let result;
      try {
        result = await pollRun(run_id);
      } catch (err) {
        setAssistantFailed(assistantId, err);
        return;
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { id: m.id, role: "assistant", status: result.status, report: result.report ?? undefined, error: result.error ?? undefined }
            : m
        )
      );

      if (result.status === "succeeded" || result.status === "failed") {
        setIsRunning(false);
        return;
      }
      setTimeout(tick, POLL_INTERVAL_MS);
    };

    setTimeout(tick, POLL_INTERVAL_MS);
  }

  return (
    <div className="flex flex-1 bg-zinc-50 dark:bg-black">
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col px-4 py-6">
        <header className="mb-4">
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
            Recruitment Assistant
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Submit a job requisition and get a ranked, scored candidate report with outreach guidance.
          </p>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {messages.length === 0 && (
            <p className="rounded-xl border border-dashed border-zinc-200 p-4 text-sm text-zinc-400 dark:border-zinc-800">
              No runs yet — fill in the form below and start one.
            </p>
          )}
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}
        </div>

        <div className="sticky bottom-0 pt-2">
          <RequisitionForm disabled={isRunning} onSubmit={handleSubmit} />
        </div>
      </div>

      <FutureFeaturesPanel />
    </div>
  );
}
