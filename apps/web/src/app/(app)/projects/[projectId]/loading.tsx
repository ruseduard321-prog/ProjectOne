/**
 * Loading state for one project.
 *
 * Distinct from the list's skeleton because the shape is genuinely different —
 * a title with a status badge, then four sections. Reusing the list skeleton
 * here would reflow the page on arrival, which is what a skeleton exists to
 * prevent ([[Design System]] §10).
 */
function SectionSkeleton() {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-6 py-5">
      <div className="flex flex-col gap-2">
        <div className="h-5 w-32 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-full max-w-prose animate-pulse rounded-sm bg-skeleton" />
      </div>
      <div className="h-10 w-full max-w-sm animate-pulse rounded-md bg-skeleton" />
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading project</span>

      <div className="flex flex-col gap-3">
        <div className="h-4 w-28 animate-pulse rounded-sm bg-skeleton" />
        <div className="flex items-start justify-between gap-3">
          <div className="h-8 w-64 animate-pulse rounded-md bg-skeleton" />
          <div className="h-7 w-24 animate-pulse rounded-full bg-skeleton" />
        </div>
      </div>

      {/* Four, matching Lifecycle, Details, Assets and Delete. */}
      <SectionSkeleton />
      <SectionSkeleton />
      <SectionSkeleton />
      <SectionSkeleton />
    </div>
  );
}
