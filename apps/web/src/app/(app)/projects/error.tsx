"use client";

import { useEffect } from "react";

import { useErrorRecovery } from "@/lib/error-recovery";

/**
 * Error boundary for the projects screens.
 *
 * Scoped to this route rather than relying on the root boundary, for the reason
 * the settings boundary states: the root boundary replaces the whole page
 * including the shell, so a failed fetch would take the navigation away with it
 * and strand the user. This one renders inside the shell.
 *
 * The message never renders `error.message` or a stack trace — an unexpected
 * failure's message is written for an engineer and is not something a user can
 * act on (CLAUDE.md §24). `digest` is surfaced so a report ties back to a server
 * log entry.
 *
 * **A project that does not exist does not reach here.** The detail page
 * converts the API's 404 into `notFound()`, so a stale link renders the
 * not-found page rather than this. What reaches this boundary is a genuine
 * failure — most likely the API being unreachable — which {@link useErrorRecovery}
 * recovers from, making the retry real rather than decorative. `reset()` alone
 * would not: it clears client state and re-renders the cached payload, which
 * still holds the failure.
 */
export default function ProjectsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retry = useErrorRecovery(reset);

  useEffect(() => {
    console.error("Projects screen failed to render", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight text-text">Projects</h1>

      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-lg border border-danger bg-surface px-6 py-5"
      >
        <h2 className="text-lg font-medium text-text">Projects could not be loaded</h2>
        <p className="max-w-prose text-sm text-text-muted">
          Your projects are safe — nothing was changed. This is usually temporary.
        </p>

        <button
          type="button"
          onClick={retry}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-contrast transition-colors hover:bg-accent-hover"
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
