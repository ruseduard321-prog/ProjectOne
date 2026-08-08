import type { ApiProjectStatus } from "@/lib/api";
import { statusLabel } from "@/lib/projects";

/**
 * A project's lifecycle state, as a badge.
 *
 * A Server Component — it renders a label and holds no state.
 *
 * ## Why the archived state is the only one styled differently
 *
 * Giving each of the nine states its own colour would be nine colour decisions
 * carrying no information: a reader cannot learn that "publishing is amber"
 * without a legend, and the label already says the state unambiguously. It would
 * also mean inventing colours outside the Design System's semantic tokens, which
 * CLAUDE.md's Design Rules forbid.
 *
 * Archived is distinguished because it is the one state that changes what a
 * project *is* rather than where it is: an archived project is finished or
 * abandoned, and a list where it looks identical to live work is a list that
 * makes the user read every label to find what is active.
 */
export interface StatusBadgeProps {
  readonly status: ApiProjectStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const archived = status === "archive";

  return (
    <span
      className={[
        "inline-flex shrink-0 items-center rounded-full border px-3 py-1 text-xs font-medium",
        archived ? "border-border text-text-muted" : "border-accent text-accent",
      ].join(" ")}
    >
      {statusLabel(status)}
    </span>
  );
}
