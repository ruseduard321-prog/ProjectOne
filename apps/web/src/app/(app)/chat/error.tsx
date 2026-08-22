"use client";

import { useEffect } from "react";

import { useErrorRecovery } from "@/lib/error-recovery";
import { PageHeader } from "@/components/shell/PageHeader";

/**
 * Error boundary for the chat screen.
 *
 * Scoped to this route rather than relying on the root boundary, for the reason
 * the projects boundary states: the root boundary replaces the whole page
 * including the shell, so a failed fetch would take the navigation away with it
 * and strand the user. This one renders inside the shell.
 *
 * The message never renders `error.message` or a stack trace — an unexpected
 * failure's message is written for an engineer and is not something a user can
 * act on (CLAUDE.md §24). `digest` is surfaced so a report ties back to a server
 * log entry.
 *
 * ## A failed *turn* does not reach here
 *
 * That is the important distinction on this screen. A provider outage, an
 * exhausted budget or a rate limit comes back through the composer's Server
 * Action and renders as a message beside the conversation, because the
 * transcript is still valid and the user's question was still saved. Replacing
 * the whole screen for an ordinary provider failure would discard what they were
 * reading and imply their conversation was lost.
 *
 * What reaches this boundary is a genuine failure to render the screen at all —
 * most likely the API being unreachable while loading the conversation list —
 * which {@link useErrorRecovery} recovers from, making the retry real rather
 * than decorative. `reset()` alone would not: it clears client state and
 * re-renders the cached payload, which still holds the failure.
 */
export default function ChatError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retry = useErrorRecovery(reset);

  useEffect(() => {
    console.error("Chat screen failed to render", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="AI Chat" />

      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-lg border border-danger bg-surface px-6 py-5"
      >
        <h2 className="text-lg font-medium text-text">Conversations could not be loaded</h2>
        <p className="max-w-prose text-sm text-text-muted">
          Your conversations are safe — nothing was changed or deleted. This is usually temporary.
        </p>

        <button
          type="button"
          onClick={retry}
          className="rounded-md bg-accent-fill px-4 py-2 text-sm font-medium text-accent-contrast transition-colors hover:bg-accent-hover"
        >
          Try again
        </button>

        {error.digest ? (
          <p className="text-xs text-text-muted">
            Reference: <span className="font-mono">{error.digest}</span>
          </p>
        ) : null}
      </div>
    </div>
  );
}
