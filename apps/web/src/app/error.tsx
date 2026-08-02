"use client";

import { useEffect } from "react";

/**
 * Root error boundary — owed since [[STEP-03 Web App Skeleton]], which
 * established `loading` and `not-found` but could not add this: Next.js
 * requires an error boundary to be a Client Component, and that step's
 * validation forbade client code.
 *
 * Shows an actionable message and a recovery affordance. It never renders
 * `error.message` or a stack trace — an unexpected failure's message is written
 * for an engineer, can carry internal detail, and is not something a user can
 * act on ([[CLAUDE|CLAUDE.md]] §24). The detail goes to the console for
 * debugging instead, and real error reporting arrives with observability work.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Preserved for debugging rather than shown. `digest` is the server-side
    // correlation id Next.js assigns, which is what ties this render to a
    // server log entry.
    console.error("Unhandled application error", error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 py-8">
      <h1 className="text-xl font-semibold tracking-tight text-text">
        Something went wrong
      </h1>
      <p className="max-w-prose text-center text-sm text-text-muted">
        The page could not be displayed. This has been logged — trying again
        often resolves it.
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-contrast transition-colors hover:bg-accent-hover"
      >
        Try again
      </button>
      {error.digest ? (
        <p className="text-xs text-text-muted">
          Reference: <span className="font-mono">{error.digest}</span>
        </p>
      ) : null}
    </main>
  );
}
