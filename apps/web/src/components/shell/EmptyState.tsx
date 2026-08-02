import type { ReactNode } from "react";

/**
 * The shell's empty state.
 *
 * Every screen inside the application will need one, and an empty state that is
 * improvised per screen is how four different versions of "nothing here yet"
 * end up shipping. Defined once, from the first surface onward, as
 * [[CLAUDE|CLAUDE.md]] §11 and [[Design System]] §10 require.
 *
 * Presentational only — no data fetching, no business logic. A Server
 * Component: nothing here needs the browser.
 */
export interface EmptyStateProps {
  /** What is empty. A short noun phrase, not a sentence. */
  readonly title: string;
  /** Why it is empty, or what to do about it. One sentence. */
  readonly description: string;
  /** Optional call to action — a link or button the caller supplies. */
  readonly action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-border bg-surface px-6 py-12 text-center">
      <h2 className="text-lg font-medium text-text">{title}</h2>
      <p className="max-w-prose text-sm text-text-muted">{description}</p>
      {action}
    </div>
  );
}
