/**
 * What the dashboard decides to show (STEP-24).
 *
 * The selection rules are asserted directly rather than through a rendered
 * component: this suite runs in a node environment with no DOM, which
 * `vitest.config.ts` justifies, and the branching is the part that can be
 * quietly wrong. A component test would need React Testing Library — a
 * dependency this step does not need to add to assert decisions that are not
 * about rendering (CLAUDE.md §28), the same reasoning `Transcript.test.ts`
 * records.
 *
 * Each case below covers a rule that a screenshot of a healthy workspace would
 * not reveal: the ranking only matters once there are more runs than rows, and
 * the budget rule only matters once a workspace has more than one budget.
 */

import { describe, expect, it } from "vitest";

import type { ApiBudget, ApiProject, ApiRunStatus, ApiWorkflowRun } from "@/lib/api";
import {
  ACTIVE_RUN_STATUSES,
  DASHBOARD_LIST_LIMIT,
  activeRuns,
  hasOpenBreaker,
  isActiveRun,
  recentProjects,
  runTimestamp,
  workspaceBudget,
} from "@/lib/dashboard";

/** A project as the API returns it. */
function project(id: string, name: string): ApiProject {
  return {
    id,
    workspace_id: "22222222-2222-2222-2222-222222222222",
    name,
    description: null,
    status: "idea",
    legal_transitions: [],
    created_by: "33333333-3333-3333-3333-333333333333",
    created_at: "2026-08-08T10:00:00+00:00",
    updated_at: "2026-08-08T10:00:00+00:00",
    version: 1,
  };
}

/** A run as the API returns it. `startedAt` is null for a queued run. */
function run(
  id: string,
  status: ApiRunStatus,
  createdAt: string,
  startedAt: string | null = null,
): ApiWorkflowRun {
  return {
    id,
    workspace_id: "22222222-2222-2222-2222-222222222222",
    workflow_type: "script_draft",
    definition_version: 1,
    status,
    project_id: null,
    detail: null,
    triggered_by: "33333333-3333-3333-3333-333333333333",
    started_at: startedAt,
    finished_at: null,
    created_at: createdAt,
    steps: [],
  };
}

/** A budget as the API returns it. `workflowType` null is the workspace-wide one. */
function budget(
  id: string,
  workflowType: string | null,
  spent: string,
  limit: string,
  breakerOpen = false,
): ApiBudget {
  return {
    id,
    workflow_type: workflowType,
    limit_usd: limit,
    spent_usd: spent,
    remaining_usd: "0.00",
    period_started_at: "2026-08-01T00:00:00+00:00",
    period_days: 30,
    breaker_open: breakerOpen,
    breaker_reason: breakerOpen ? "Ceiling reached" : null,
  };
}

describe("recent projects", () => {
  it("caps the list at five", () => {
    const projects = Array.from({ length: 9 }, (_, index) => project(`p${index}`, `Project ${index}`));

    expect(recentProjects(projects)).toHaveLength(DASHBOARD_LIST_LIMIT);
  });

  it("preserves the order the API returned, rather than sorting again", () => {
    /*
     * The server already returns newest first. A second sort here would be a
     * second copy of an ordering rule, and two copies diverge the first time one
     * changes — the defect `lib/projects.ts` avoids by refusing to hold the
     * transition rules. Deliberately non-alphabetical so a re-sort would show.
     */
    const projects = [project("p1", "Zebra"), project("p2", "Apple"), project("p3", "Mango")];

    expect(recentProjects(projects).map((each) => each.name)).toEqual(["Zebra", "Apple", "Mango"]);
  });

  it("returns everything when there are fewer than five", () => {
    expect(recentProjects([project("p1", "Only one")])).toHaveLength(1);
  });
});

describe("which runs count as active", () => {
  it("includes exactly the three states blocked on time or on a human", () => {
    expect([...ACTIVE_RUN_STATUSES]).toEqual(["awaiting_approval", "running", "pending"]);
  });

  it("excludes completed and failed runs", () => {
    // A finished run is history, not something needing attention. If either of
    // these leaked in, the section would fill with noise on any busy workspace.
    expect(isActiveRun(run("r1", "completed", "2026-08-10T10:00:00+00:00"))).toBe(false);
    expect(isActiveRun(run("r2", "failed", "2026-08-10T10:00:00+00:00"))).toBe(false);
  });

  it("keeps the three active states", () => {
    expect(isActiveRun(run("r1", "awaiting_approval", "2026-08-10T10:00:00+00:00"))).toBe(true);
    expect(isActiveRun(run("r2", "running", "2026-08-10T10:00:00+00:00"))).toBe(true);
    expect(isActiveRun(run("r3", "pending", "2026-08-10T10:00:00+00:00"))).toBe(true);
  });
});

describe("how active runs are ranked", () => {
  it("puts awaiting approval first, then running, then queued", () => {
    const ranked = activeRuns([
      run("queued", "pending", "2026-08-10T10:00:00+00:00"),
      run("running", "running", "2026-08-10T10:00:00+00:00"),
      run("blocked", "awaiting_approval", "2026-08-10T10:00:00+00:00"),
    ]);

    expect(ranked.map((each) => each.id)).toEqual(["blocked", "running", "queued"]);
  });

  it("puts the newest first within one status", () => {
    const ranked = activeRuns([
      run("older", "running", "2026-08-10T09:00:00+00:00"),
      run("newer", "running", "2026-08-10T11:00:00+00:00"),
    ]);

    expect(ranked.map((each) => each.id)).toEqual(["newer", "older"]);
  });

  it("applies the cap after ranking, never before", () => {
    /*
     * **The case this whole ordering exists for.** Six running jobs arrive ahead
     * of the one run actually blocked on the user. Capping first would keep the
     * six and drop the approval — hiding the single item this section exists to
     * surface, on exactly the busy workspace where it matters most.
     */
    const ranked = activeRuns([
      ...Array.from({ length: 6 }, (_, index) =>
        run(`running-${index}`, "running", "2026-08-10T10:00:00+00:00"),
      ),
      run("blocked", "awaiting_approval", "2026-08-10T08:00:00+00:00"),
    ]);

    expect(ranked).toHaveLength(DASHBOARD_LIST_LIMIT);
    expect(ranked[0]?.id).toBe("blocked");
  });

  it("filters before capping, so finished runs never consume a row", () => {
    const ranked = activeRuns([
      ...Array.from({ length: 5 }, (_, index) =>
        run(`done-${index}`, "completed", "2026-08-10T12:00:00+00:00"),
      ),
      run("live", "running", "2026-08-10T10:00:00+00:00"),
    ]);

    expect(ranked.map((each) => each.id)).toEqual(["live"]);
  });

  it("does not mutate the array it was given", () => {
    // `sort` is in-place, so sorting the caller's array would reorder the props
    // a component was handed. The copy is what makes that safe.
    const runs = [
      run("queued", "pending", "2026-08-10T10:00:00+00:00"),
      run("blocked", "awaiting_approval", "2026-08-10T10:00:00+00:00"),
    ];

    activeRuns(runs);

    expect(runs.map((each) => each.id)).toEqual(["queued", "blocked"]);
  });
});

describe("which timestamp a run shows", () => {
  it("shows the start time, labelled as started, once a run has begun", () => {
    expect(runTimestamp(run("r1", "running", "2026-08-10T09:00:00+00:00", "2026-08-10T09:05:00+00:00"))).toEqual({
      at: "2026-08-10T09:05:00+00:00",
      label: "Started",
    });
  });

  it("falls back to the creation time, labelled as queued, for a run that has not started", () => {
    /*
     * `started_at` is null on a pending run by design. Showing its creation time
     * under a "Started" label would state something untrue about precisely the
     * runs where "how long has this been waiting" is the question being asked.
     */
    expect(runTimestamp(run("r1", "pending", "2026-08-10T09:00:00+00:00", null))).toEqual({
      at: "2026-08-10T09:00:00+00:00",
      label: "Queued",
    });
  });
});

describe("the budget glance", () => {
  it("reads the workspace-wide budget, the one with no workflow type", () => {
    const found = workspaceBudget([
      budget("b1", "script_draft", "5.00", "10.00"),
      budget("b2", null, "12.00", "100.00"),
    ]);

    expect(found?.id).toBe("b2");
  });

  it("never sums budgets, because per-workflow budgets draw against the same spend", () => {
    /*
     * **The defect a single-budget fixture would never catch.** The endpoint
     * returns the workspace-wide budget alongside per-workflow ones that draw
     * against the same money. Adding them would report $22.00 spent when $12.00
     * left the account — a page whose entire purpose is being trusted about
     * money, displaying a figure that is simply wrong.
     */
    const found = workspaceBudget([
      budget("b1", null, "12.00", "100.00"),
      budget("b2", "script_draft", "5.00", "10.00"),
      budget("b3", "chat", "5.00", "10.00"),
    ]);

    expect(found?.spent_usd).toBe("12.00");
    expect(found?.limit_usd).toBe("100.00");
  });

  it("reports none when only per-workflow budgets exist", () => {
    // The caller renders an honest "not configured" state. It must not fall back
    // to a per-workflow budget and present it as though it covered the workspace.
    expect(workspaceBudget([budget("b1", "script_draft", "5.00", "10.00")])).toBeUndefined();
  });

  it("reports none when there are no budgets at all", () => {
    expect(workspaceBudget([])).toBeUndefined();
  });
});

describe("the circuit breaker warning", () => {
  it("warns when the workspace-wide budget has tripped", () => {
    expect(hasOpenBreaker([budget("b1", null, "100.00", "100.00", true)])).toBe(true);
  });

  it("warns when only a per-workflow budget has tripped", () => {
    /*
     * Owner-approved scope: the warning fires on *any* budget. A tripped
     * per-workflow breaker is refusing work right now, and a home surface that
     * stayed silent because the workspace-wide budget looked healthy would be
     * the silent failure §15a exists to prevent.
     */
    expect(
      hasOpenBreaker([
        budget("b1", null, "10.00", "100.00", false),
        budget("b2", "script_draft", "10.00", "10.00", true),
      ]),
    ).toBe(true);
  });

  it("warns even when no workspace-wide budget is configured", () => {
    // The warning and the spend line are independent: this workspace renders
    // "not configured" *and* the warning, and both are true.
    expect(hasOpenBreaker([budget("b1", "script_draft", "10.00", "10.00", true)])).toBe(true);
  });

  it("stays silent when every breaker is closed", () => {
    expect(
      hasOpenBreaker([budget("b1", null, "10.00", "100.00"), budget("b2", "chat", "1.00", "10.00")]),
    ).toBe(false);
  });

  it("stays silent when there are no budgets", () => {
    expect(hasOpenBreaker([])).toBe(false);
  });
});
