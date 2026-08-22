"use client";

import { useEffect } from "react";

import { useErrorRecovery } from "@/lib/error-recovery";
import { PageHeader } from "@/components/shell/PageHeader";

/**
 * Error boundary for the settings screen.
 *
 * Scoped to this route rather than relying on the root boundary, and the
 * difference is what the user is left with: the root boundary replaces the whole
 * page including the shell, so a failed settings fetch would take the navigation
 * away with it and strand the user. This one renders inside the shell, so they
 * can move to another section instead of reloading.
 *
 * The message is actionable and names what failed. It never renders
 * `error.message` or a stack trace: an unexpected failure's message is written
 * for an engineer, may carry internal detail, and is not something a user can
 * act on (CLAUDE.md §24). `digest` is surfaced so a user's report ties back to a
 * server log entry.
 *
 * This page reads provider credentials and spend, so the most likely failure is
 * the API being unreachable — which {@link useErrorRecovery} genuinely recovers
 * from, making the retry affordance real rather than decorative. `reset()` alone
 * would not: it clears client state and re-renders the cached payload, which
 * still holds the failure.
 */
export default function SettingsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retry = useErrorRecovery(reset);

  useEffect(() => {
    console.error("Settings screen failed to render", error);
  }, [error]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Settings" />

      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-lg border border-danger bg-surface px-6 py-5"
      >
        <h2 className="text-lg font-medium text-text">Settings could not be loaded</h2>
        <p className="max-w-prose text-sm text-text-muted">
          Your settings are safe — nothing was changed. This is usually temporary.
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
