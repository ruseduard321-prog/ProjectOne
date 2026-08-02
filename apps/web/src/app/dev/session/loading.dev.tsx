/**
 * Loading skeleton for the session inspector.
 *
 * The page calls `/auth/me` and `/health`, so there is a real wait to cover —
 * and a diagnostics page that appears blank while those are in flight looks
 * exactly like a diagnostics page reporting an empty session, which is the one
 * misreading it must not invite.
 *
 * Uses `--color-skeleton` rather than `--color-surface-raised`: STEP-15 found
 * that a surface token reused as a fill *on* that surface renders invisible in
 * light mode (1.05 contrast). A token naming a surface is not automatically
 * safe as a fill on it (Design System §6.2).
 */
export default function Loading() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-8">
        <div className="h-8 w-64 animate-pulse rounded bg-skeleton" />
        <div className="mt-3 h-4 w-full max-w-2xl animate-pulse rounded bg-skeleton" />
      </div>

      {[0, 1, 2].map((section) => (
        <section key={section} className="mb-8">
          <div className="mb-2 h-6 w-40 animate-pulse rounded bg-skeleton" />
          <div className="rounded-lg border border-border bg-surface px-4">
            {[0, 1, 2].map((row) => (
              <div
                key={row}
                className="grid grid-cols-1 gap-1 border-b border-border py-3 sm:grid-cols-[16rem_1fr] sm:gap-4"
              >
                <div className="h-4 w-32 animate-pulse rounded bg-skeleton" />
                <div className="h-4 w-56 animate-pulse rounded bg-skeleton" />
              </div>
            ))}
          </div>
        </section>
      ))}

      <span className="sr-only">Loading session diagnostics…</span>
    </main>
  );
}
