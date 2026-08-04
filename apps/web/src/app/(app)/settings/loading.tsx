/**
 * Loading state for the settings screen.
 *
 * More specific than the shell's own `loading.tsx` deliberately: this page makes
 * four concurrent API round trips, so its loading state is the one users will
 * actually see, and a skeleton that holds the shape of four sections stops the
 * page reflowing when they land ([[Design System]] §10).
 *
 * Built entirely from semantic tokens. `bg-skeleton` exists because STEP-15
 * found that reusing a *surface* token as a fill on that surface produced an
 * invisible result — a token naming a surface is not automatically safe as a
 * fill on it (§6.5).
 */
function SectionSkeleton() {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-6 py-5">
      <div className="flex flex-col gap-2">
        <div className="h-5 w-40 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-full max-w-prose animate-pulse rounded-sm bg-skeleton" />
      </div>

      <div className="h-10 w-full max-w-sm animate-pulse rounded-md bg-skeleton" />
      <div className="h-9 w-32 animate-pulse rounded-md bg-skeleton" />
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading settings</span>

      <div className="flex flex-col gap-2">
        <div className="h-8 w-40 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-72 animate-pulse rounded-sm bg-skeleton" />
      </div>

      {/*
       * Four, matching the four sections the page renders. A skeleton with a
       * different shape to its content is a skeleton that causes the reflow it
       * exists to prevent.
       */}
      <SectionSkeleton />
      <SectionSkeleton />
      <SectionSkeleton />
      <SectionSkeleton />
    </div>
  );
}
