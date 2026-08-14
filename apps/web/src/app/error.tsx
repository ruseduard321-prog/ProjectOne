"use client";

import { useEffect } from "react";

import { useErrorRecovery } from "@/lib/error-recovery";

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
 *
 * Recovery goes through {@link useErrorRecovery} rather than `reset` alone
 * (FA-04). `reset()` only clears client state and re-renders the cached payload
 * — the failure is still in it, so the boundary renders again and nothing
 * changes. STEP-24 fixed that in all four route boundaries and left this one
 * behind, which matters because a route boundary cannot catch a failure in the
 * layout that wraps it: this is the boundary that renders during the API outage
 * [[STEP-16b Auth Refresh Outage Handling]] handles, and its retry was inert.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const retry = useErrorRecovery(reset);

  useEffect(() => {
    // Preserved for debugging rather than shown. `digest` is the server-side
    // correlation id Next.js assigns, which is what ties this render to a
    // server log entry.
    console.error("Unhandled application error", error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-8">
      {/*
        `role="alert"` so assistive technology announces the failure (FA-11).
        All four route boundaries carry it; this one carried no role at all, so
        a screen-reader user reaching the outage path was told nothing. Placed
        on the container that holds the message rather than on `<main>`, which
        is the arrangement the route boundaries already use.
      */}
      <div role="alert" className="flex flex-col items-center gap-4">
        <h1 className="text-xl font-semibold tracking-tight text-text">
          Something went wrong
        </h1>
        <p className="max-w-prose text-center text-sm text-text-muted">
          The page could not be displayed. This has been logged — trying again
          often resolves it.
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
    </main>
  );
}
