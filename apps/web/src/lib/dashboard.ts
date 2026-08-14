/**
 * The dashboard's selection rules (STEP-24).
 *
 * Pure functions over API responses, holding every decision the home surface
 * makes about *what to show*. They live here rather than inside the components
 * for the reason `Transcript.test.ts` records: the web suite runs in a node
 * environment with no DOM, so logic asserted directly needs no React Testing
 * Library — a dependency this step would otherwise add to test branching that
 * is not about rendering at all (CLAUDE.md §28).
 *
 * Each rule below is one line of the approved STEP-24 plan. They are worth
 * stating in one module because each is quietly wrong in a way a screenshot
 * would not reveal.
 */

import type { ApiBudget, ApiProject, ApiRunStatus, ApiWorkflowRun } from "@/lib/api";

/**
 * How many rows each summary list shows.
 *
 * The cap is what makes this page a summary rather than a second copy of the
 * list pages, so every capped section also links to the surface holding the rest.
 */
export const DASHBOARD_LIST_LIMIT = 5;

/**
 * The run states this page treats as active, in the order it ranks them.
 *
 * `awaiting_approval` leads because it is the only one of the three blocked on
 * the user: a run waiting for a human is the literal answer to "what needs
 * attention", which is this page's whole purpose. `completed` and `failed` are
 * absent because a finished run is not active — they are history, and history
 * belongs on a surface built to show it.
 */
export const ACTIVE_RUN_STATUSES: readonly ApiRunStatus[] = [
  "awaiting_approval",
  "running",
  "pending",
];

/**
 * The most recent projects, capped.
 *
 * **The API's ordering is preserved rather than recomputed.** The server already
 * returns newest first; sorting again here would be a second copy of an ordering
 * rule, and two copies diverge the first time one changes — the same reasoning
 * that keeps the lifecycle transition rules out of the frontend
 * (`lib/projects.ts`).
 */
export function recentProjects(
  projects: readonly ApiProject[],
  limit: number = DASHBOARD_LIST_LIMIT,
): readonly ApiProject[] {
  return projects.slice(0, limit);
}

/** Whether a run is one this page considers active. */
export function isActiveRun(run: ApiWorkflowRun): boolean {
  return ACTIVE_RUN_STATUSES.includes(run.status);
}

/**
 * When a run happened, and what that time actually means.
 *
 * `started_at` is nullable on the API's response and a pending run has not
 * started, so the label follows the field rather than being fixed. Showing a
 * creation time under a "Started" label would state something untrue about
 * exactly the runs — queued ones — where the elapsed time is the thing the user
 * is trying to read.
 */
export interface RunTimestamp {
  readonly at: string;
  readonly label: "Started" | "Queued";
}

export function runTimestamp(run: ApiWorkflowRun): RunTimestamp {
  return run.started_at === null
    ? { at: run.created_at, label: "Queued" }
    : { at: run.started_at, label: "Started" };
}

/**
 * The active runs this page shows: filtered, ranked, then capped.
 *
 * **The cap is applied last, and that ordering is the point.** Capping before
 * ranking would show the five runs that happened to arrive first rather than the
 * five most deserving of attention — so a workspace with six running jobs and
 * one awaiting approval could hide the only item actually blocked on the user,
 * which is the single thing this section exists to surface.
 *
 * Within one status the newest run leads, matching how every other list in the
 * product reads.
 */
export function activeRuns(
  runs: readonly ApiWorkflowRun[],
  limit: number = DASHBOARD_LIST_LIMIT,
): readonly ApiWorkflowRun[] {
  return runs
    .filter(isActiveRun)
    .slice()
    .sort((left, right) => {
      const byStatus =
        ACTIVE_RUN_STATUSES.indexOf(left.status) - ACTIVE_RUN_STATUSES.indexOf(right.status);

      if (byStatus !== 0) {
        return byStatus;
      }

      // Newest first within a status. Compared as ISO-8601 strings, which sort
      // lexicographically in chronological order — and never parsed to a Date,
      // which would turn an ordering into a timezone question.
      return right.created_at.localeCompare(left.created_at);
    })
    .slice(0, limit);
}

/**
 * The workspace-wide budget — the one whose `workflow_type` is null — or
 * `undefined` when none is configured.
 *
 * **Exactly one budget, never a sum.** The endpoint returns the workspace-wide
 * budget alongside per-workflow-type budgets that draw against the same spend,
 * so adding them together would count the same dollars more than once and
 * display a figure that is simply wrong. A page whose purpose is to be trusted
 * about money does not approximate it.
 */
export function workspaceBudget(budgets: readonly ApiBudget[]): ApiBudget | undefined {
  return budgets.find((budget) => budget.workflow_type === null);
}

/**
 * Whether any returned budget has tripped its circuit breaker.
 *
 * **Any budget, not only the workspace-wide one.** A tripped per-workflow
 * breaker is refusing work right now whether or not a workspace-wide budget
 * exists, and a home surface that stayed silent about it would be the exact
 * silent failure CLAUDE.md §15a's graceful-degradation rule exists to prevent.
 *
 * The reason text is deliberately not part of this answer: the warning says that
 * work is paused and where to go, and the diagnostic detail lives on the
 * settings screen built to show it.
 */
export function hasOpenBreaker(budgets: readonly ApiBudget[]): boolean {
  return budgets.some((budget) => budget.breaker_open);
}
