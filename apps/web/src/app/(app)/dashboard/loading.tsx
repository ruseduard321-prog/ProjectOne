/**
 * Loading state for the dashboard.
 *
 * The shape mirrors what the page renders — heading, spend line, then the two
 * capped lists — because a skeleton with a different shape to its content causes
 * the reflow it exists to prevent ([[Design System]] §10).
 *
 * Two placeholder rows per list rather than the cap of five: the real count is
 * unknown before the fetch, and drawing five when most workspaces will show one
 * or two would collapse rather than settle.
 */
function RowSkeleton() {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface px-6 py-5">
      <div className="flex flex-col gap-2">
        <div className="h-5 w-48 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-32 animate-pulse rounded-sm bg-skeleton" />
      </div>
      <div className="h-6 w-24 animate-pulse rounded-full bg-skeleton" />
    </div>
  );
}

function SectionSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="h-6 w-40 animate-pulse rounded-md bg-skeleton" />
      <RowSkeleton />
      <RowSkeleton />
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading dashboard</span>

      <div className="flex flex-col gap-2">
        <div className="h-8 w-44 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-72 animate-pulse rounded-sm bg-skeleton" />
      </div>

      <div className="flex flex-col gap-3">
        <div className="h-6 w-28 animate-pulse rounded-md bg-skeleton" />
        <div className="h-16 w-full animate-pulse rounded-lg bg-skeleton" />
      </div>

      <SectionSkeleton />
      <SectionSkeleton />
    </div>
  );
}
