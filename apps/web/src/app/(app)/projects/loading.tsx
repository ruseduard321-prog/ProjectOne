/**
 * Loading state for the projects list.
 *
 * The shape mirrors what the page renders — a heading, the create form, then a
 * list of cards — because a skeleton with a different shape to its content
 * causes the reflow it exists to prevent ([[Design System]] §10).
 *
 * Three placeholder rows rather than a guess at the real count: the number is
 * unknown before the fetch, and three reads as "a list is coming" without
 * implying a length.
 */
function CardSkeleton() {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface px-6 py-5">
      <div className="flex flex-col gap-2">
        <div className="h-5 w-48 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-64 animate-pulse rounded-sm bg-skeleton" />
      </div>
      <div className="h-6 w-20 animate-pulse rounded-full bg-skeleton" />
    </div>
  );
}

export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading projects</span>

      <div className="flex flex-col gap-2">
        <div className="h-8 w-40 animate-pulse rounded-md bg-skeleton" />
        <div className="h-4 w-72 animate-pulse rounded-sm bg-skeleton" />
      </div>

      <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface px-6 py-5">
        <div className="h-5 w-32 animate-pulse rounded-md bg-skeleton" />
        <div className="h-10 w-full max-w-sm animate-pulse rounded-md bg-skeleton" />
        <div className="h-9 w-36 animate-pulse rounded-md bg-skeleton" />
      </div>

      <CardSkeleton />
      <CardSkeleton />
      <CardSkeleton />
    </div>
  );
}
