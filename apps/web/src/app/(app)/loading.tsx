/**
 * Loading state for every screen inside the application shell.
 *
 * A skeleton rather than a spinner: it holds the shape of the content that is
 * coming, so the page does not reflow when it arrives ([[Design System]] §10).
 * Built from semantic tokens — a skeleton is the easiest place to accidentally
 * hardcode a grey.
 *
 * The shell chrome itself does not re-render during navigation, so this covers
 * the page area only.
 */
export default function Loading() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy="true">
      <span className="sr-only">Loading</span>

      <div className="h-8 w-48 animate-pulse rounded-md bg-skeleton" />

      <div className="flex flex-col gap-3">
        <div className="h-4 w-full max-w-prose animate-pulse rounded-sm bg-skeleton" />
        <div className="h-4 w-full max-w-prose animate-pulse rounded-sm bg-skeleton" />
        <div className="h-4 w-2/3 max-w-prose animate-pulse rounded-sm bg-skeleton" />
      </div>
    </div>
  );
}
