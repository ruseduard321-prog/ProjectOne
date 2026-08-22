"use client";

import { useEffect } from "react";

import { useErrorRecovery } from "@/lib/error-recovery";
import { PageHeader } from "@/components/shell/PageHeader";

/**
 * Error boundary for the dashboard.
 *
 * Scoped to this route rather than relying on the root boundary, for the reason
 * the projects and settings boundaries state: the root boundary replaces the
 * whole page including the shell, so a failed fetch would take the navigation
 * away with it and strand the user on the one screen whose job is to send them
 * somewhere else. This one renders inside the shell.
 *
 * The message never renders `error.message` or a stack trace — an unexpected
 * failure's message is written for an engineer and is not something a user can
 * act on (CLAUDE.md §24). `digest` is surfaced so a report ties back to a server
 * log entry.
 *
 * This page fetches three independent resources, so any one of them failing
 * lands here. The retry refetches all three, which is the honest recovery: the
 * boundary cannot know which one failed, and offering a partial retry would
 * imply knowledge it does not have.
 *
 * Recovery goes through {@link useErrorRecovery} rather than `reset` alone.
 * `reset()` only clears client state and re-renders the cached payload — the
 * failure is still in it, so the boundary renders again and nothing changes.
 */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retry = useErrorRecovery(reset);

  useEffect(() => {
    console.error("Dashboard failed to render", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Dashboard" />

      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-lg border border-danger bg-surface px-6 py-5"
      >
        <h2 className="text-lg font-medium text-text">Your dashboard could not be loaded</h2>
        <p className="max-w-prose text-sm text-text-muted">
          Nothing was changed — your projects and workflows are safe. This is usually temporary.
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
