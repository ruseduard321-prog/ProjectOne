/**
 * What the dashboard actually renders (STEP-24).
 *
 * ## Why these exist alongside `lib/dashboard.test.ts`
 *
 * The selection tests assert what the page *decides*. They cannot assert that
 * anything renders the decision, and the difference is not theoretical: with the
 * breaker warning's JSX disabled outright, the entire 192-test suite still
 * passed. `hasOpenBreaker` kept returning `true`, nothing consumed it, and no
 * test noticed. A reviewer found the gap; this file closes it.
 *
 * Both layers are kept. The selection tests state the rules precisely and fail
 * with a readable message when a rule is wrong; these prove the rules reach the
 * screen. Deleting either would leave a class of defect uncovered.
 *
 * ## Why `renderToStaticMarkup` and not React Testing Library
 *
 * The suite runs in a node environment with no DOM (`vitest.config.ts`).
 * `react-dom` is already a dependency, and `renderToStaticMarkup` produces the
 * markup a Server Component emits — which is the whole of what this page does,
 * since none of it is interactive. RTL plus jsdom would be two dependencies
 * added to assert strings that are already available without them (CLAUDE.md
 * §28).
 *
 * Assertions are on rendered text and hrefs rather than on class names: the
 * former is what a user reads, the latter changes with every styling tweak.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DashboardScreen } from "@/app/(app)/dashboard/page";
import type { ApiBudget, ApiProject, ApiRunStatus, ApiWorkflowRun } from "@/lib/api";

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

function run(
  id: string,
  status: ApiRunStatus,
  createdAt: string,
  startedAt: string | null = null,
  workflowType = "script_draft",
): ApiWorkflowRun {
  return {
    id,
    workspace_id: "22222222-2222-2222-2222-222222222222",
    workflow_type: workflowType,
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

function budget(
  id: string,
  workflowType: string | null,
  spent: string,
  limit: string,
  breakerOpen = false,
  breakerReason: string | null = null,
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
    breaker_reason: breakerReason,
  };
}

/** Render the screen with everything empty unless a case overrides it. */
function render(
  overrides: {
    readonly workspaceName?: string;
    readonly otherWorkspaceCount?: number;
    readonly projects?: readonly ApiProject[];
    readonly runs?: readonly ApiWorkflowRun[];
    readonly budgets?: readonly ApiBudget[];
  } = {},
): string {
  return renderToStaticMarkup(
    <DashboardScreen
      workspaceName={overrides.workspaceName ?? "Acme"}
      otherWorkspaceCount={overrides.otherWorkspaceCount ?? 0}
      projects={overrides.projects ?? []}
      runs={overrides.runs ?? []}
      budgets={overrides.budgets ?? []}
    />,
  );
}

/** Rendered markup with entities decoded, so assertions read as prose. */
function text(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;|&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&#x2F;/g, "/")
    .replace(/\s+/g, " ");
}

describe("the empty states", () => {
  it("says there are no projects yet, and offers the way to create one", () => {
    const rendered = text(render({ projects: [] }));

    expect(rendered).toContain("No projects yet");
    expect(rendered).toContain("Create your first project");
  });

  it("says no workflows are running", () => {
    const rendered = text(render({ runs: [] }));

    expect(rendered).toContain("No workflows running");
  });

  it("distinguishes the two, rather than collapsing to one page-level empty state", () => {
    // "No projects yet" and "no workflows running" are different facts about a
    // workspace, and a user needs to tell them apart.
    const rendered = text(render());

    expect(rendered).toContain("No projects yet");
    expect(rendered).toContain("No workflows running");
  });
});

describe("the budget glance", () => {
  it("renders spend against the workspace-wide ceiling", () => {
    const rendered = text(
      render({
        budgets: [budget("b1", null, "12.00", "100.00")],
      }),
    );

    expect(rendered).toContain("$12.00");
    expect(rendered).toContain("$100.00");
  });

  it("renders the workspace-wide figures, never the sum of every budget", () => {
    /*
     * The double-counting defect, asserted on the *rendered output* rather than
     * on the selector alone. Per-workflow budgets draw against the same spend,
     * so a page showing $22.00 would report money that never left the account.
     */
    const rendered = text(
      render({
        budgets: [
          budget("b1", null, "12.00", "100.00"),
          budget("b2", "script_draft", "5.00", "10.00"),
          budget("b3", "chat", "5.00", "10.00"),
        ],
      }),
    );

    expect(rendered).toContain("$12.00");
    expect(rendered).not.toContain("$22.00");
    expect(rendered).not.toContain("$120.00");
  });

  it("renders the honest not-configured state when no workspace-wide budget exists", () => {
    const rendered = text(
      render({ budgets: [budget("b1", "script_draft", "5.00", "10.00")] }),
    );

    expect(rendered).toContain("No workspace-wide AI budget configured");
  });

  it("does not present a per-workflow budget as though it covered the workspace", () => {
    // The failure mode the not-configured state exists to prevent: showing
    // "$5.00 of $10.00" would state a ceiling the workspace does not have.
    const rendered = text(
      render({ budgets: [budget("b1", "script_draft", "5.00", "10.00")] }),
    );

    expect(rendered).not.toContain("$5.00 of $10.00");
  });
});

describe("the circuit breaker warning", () => {
  it("renders when the workspace-wide budget has tripped", () => {
    const rendered = text(
      render({ budgets: [budget("b1", null, "100.00", "100.00", true, "Ceiling reached")] }),
    );

    expect(rendered).toContain("One or more AI workflows are paused by a spending limit");
  });

  it("renders when only a per-workflow budget has tripped", () => {
    /*
     * **The case the mutation test exposed.** A healthy workspace-wide budget
     * beside a tripped per-workflow one: work is being refused right now, and a
     * home surface that stayed quiet would be the silent failure §15a forbids.
     */
    const rendered = text(
      render({
        budgets: [
          budget("b1", null, "10.00", "100.00", false),
          budget("b2", "script_draft", "10.00", "10.00", true, "Ceiling reached"),
        ],
      }),
    );

    expect(rendered).toContain("One or more AI workflows are paused by a spending limit");
  });

  it("renders alongside the not-configured state, because both are true at once", () => {
    // Owner-approved scope: the warning and the spend line are independent. A
    // workspace with no workspace-wide budget and a tripped per-workflow one
    // shows both, and neither suppresses the other.
    const rendered = text(
      render({
        budgets: [budget("b1", "script_draft", "10.00", "10.00", true, "Ceiling reached")],
      }),
    );

    expect(rendered).toContain("One or more AI workflows are paused by a spending limit");
    expect(rendered).toContain("No workspace-wide AI budget configured");
  });

  it("never renders the breaker reason", () => {
    /*
     * The reason is internal diagnostic state. The home surface says work is
     * paused and where to go; the detail belongs on the settings screen built to
     * show it. A reason string is also the most likely place for an internal
     * identifier to leak into a user-facing page.
     */
    const rendered = text(
      render({
        budgets: [
          budget("b1", null, "100.00", "100.00", true, "internal-quota-daemon-4417 tripped"),
        ],
      }),
    );

    expect(rendered).toContain("One or more AI workflows are paused by a spending limit");
    expect(rendered).not.toContain("internal-quota-daemon-4417");
    expect(rendered).not.toContain("tripped");
  });

  it("stays silent when every breaker is closed", () => {
    const rendered = text(render({ budgets: [budget("b1", null, "10.00", "100.00")] }));

    expect(rendered).not.toContain("paused by a spending limit");
  });
});

describe("active workflows in the rendered output", () => {
  it("renders a run that is awaiting approval, labelled as such", () => {
    const rendered = text(
      render({ runs: [run("r1", "awaiting_approval", "2026-08-10T10:00:00+00:00")] }),
    );

    expect(rendered).toContain("Awaiting approval");
  });

  it("does not render completed or failed runs", () => {
    const rendered = text(
      render({
        runs: [
          run("done", "completed", "2026-08-10T10:00:00+00:00", null, "finished_workflow"),
          run("broken", "failed", "2026-08-10T10:00:00+00:00", null, "failed_workflow"),
        ],
      }),
    );

    expect(rendered).not.toContain("finished_workflow");
    expect(rendered).not.toContain("failed_workflow");
    // With nothing active left, the empty state is what should appear.
    expect(rendered).toContain("No workflows running");
  });

  it("renders the newest run first within one status", () => {
    const rendered = text(
      render({
        runs: [
          run("older", "running", "2026-08-10T09:00:00+00:00", null, "older_run"),
          run("newer", "running", "2026-08-10T11:00:00+00:00", null, "newer_run"),
        ],
      }),
    );

    expect(rendered.indexOf("newer_run")).toBeLessThan(rendered.indexOf("older_run"));
  });

  it("renders the blocked run ahead of the running ones", () => {
    const rendered = text(
      render({
        runs: [
          run("running", "running", "2026-08-10T10:00:00+00:00", "2026-08-10T10:00:00+00:00", "running_one"),
          run("blocked", "awaiting_approval", "2026-08-10T09:00:00+00:00", null, "blocked_one"),
        ],
      }),
    );

    expect(rendered.indexOf("blocked_one")).toBeLessThan(rendered.indexOf("running_one"));
  });

  it("renders at most five runs, keeping the one that needs a human", () => {
    /*
     * The cap-after-ranking rule, proved on the output. Six running jobs arrive
     * ahead of one awaiting approval: if the cap were applied first, the
     * approval — the only item blocked on the user — would not appear at all.
     */
    const rendered = text(
      render({
        runs: [
          ...Array.from({ length: 6 }, (_, index) =>
            run(`r${index}`, "running", "2026-08-10T10:00:00+00:00", null, `running_${index}`),
          ),
          run("blocked", "awaiting_approval", "2026-08-10T08:00:00+00:00", null, "blocked_one"),
        ],
      }),
    );

    expect(rendered).toContain("blocked_one");
    // Five rows total: the approval plus four of the six running jobs.
    const shown = Array.from({ length: 6 }, (_, index) => `running_${index}`).filter((name) =>
      rendered.includes(name),
    );
    expect(shown).toHaveLength(4);
  });

  it("labels a started run's time as started, and a queued one's as queued", () => {
    const started = text(
      render({
        runs: [run("r1", "running", "2026-08-10T09:00:00+00:00", "2026-08-10T09:05:00+00:00")],
      }),
    );
    expect(started).toContain("Started");
    expect(started).toContain("2026-08-10T09:05:00+00:00");

    const queued = text(render({ runs: [run("r2", "pending", "2026-08-10T09:00:00+00:00", null)] }));
    expect(queued).toContain("Queued");
    expect(queued).toContain("2026-08-10T09:00:00+00:00");
  });

  it("links no run anywhere, because no workflow route exists", () => {
    // A row linking to an invented route would be a dead control. The section
    // renders runs as text until a workflow surface exists to link to.
    const html = render({
      runs: [run("r1", "awaiting_approval", "2026-08-10T10:00:00+00:00")],
    });

    expect(html).not.toContain('href="/workflows');
    expect(html).not.toContain('href="/runs');
  });
});

describe("recent projects in the rendered output", () => {
  it("renders each project, linking to its own page", () => {
    const html = render({ projects: [project("p1", "Spring campaign")] });

    expect(text(html)).toContain("Spring campaign");
    expect(html).toContain('href="/projects/p1"');
  });

  it("renders them in the order the API returned, rather than re-sorting", () => {
    // The server orders newest first. A client-side sort would be a second copy
    // of that rule; these names are deliberately non-alphabetical so one shows.
    const rendered = text(
      render({
        projects: [project("p1", "Zebra"), project("p2", "Apple"), project("p3", "Mango")],
      }),
    );

    expect(rendered.indexOf("Zebra")).toBeLessThan(rendered.indexOf("Apple"));
    expect(rendered.indexOf("Apple")).toBeLessThan(rendered.indexOf("Mango"));
  });

  it("renders at most five, and links to the full list", () => {
    const html = render({
      projects: Array.from({ length: 9 }, (_, index) => project(`p${index}`, `Project ${index}`)),
    });
    const rendered = text(html);

    const shown = Array.from({ length: 9 }, (_, index) => `Project ${index}`).filter((name) =>
      rendered.includes(name),
    );

    expect(shown).toHaveLength(5);
    expect(html).toContain('href="/projects"');
    expect(rendered).toContain("All projects");
  });
});

describe("quick actions", () => {
  it("renders exactly the three approved destinations", () => {
    const html = render();
    const rendered = text(html);

    expect(rendered).toContain("Projects");
    expect(rendered).toContain("AI Chat");
    expect(rendered).toContain("Settings");

    expect(html).toContain('href="/projects"');
    expect(html).toContain('href="/chat"');
    expect(html).toContain('href="/settings"');
  });

  it("offers nothing whose destination does not exist in this build", () => {
    /*
     * The Dashboard specification also names Create Project, Upload Files,
     * Review Approvals and View Analytics. None has a route, and rendering them
     * as controls would be a menu of things that do not work (CLAUDE.md §35).
     */
    const html = render();

    expect(html).not.toContain('href="/analytics');
    expect(html).not.toContain('href="/upload');
    expect(html).not.toContain('href="/approvals');
    expect(text(html)).not.toContain("View Analytics");
    expect(text(html)).not.toContain("Upload Files");
  });
});

describe("the honest stubs", () => {
  it("renders both, each labelled as not available yet", () => {
    const rendered = text(render());

    expect(rendered).toContain("Notifications");
    expect(rendered).toContain("AI recommendations");
    // Two sections, both stating the same honest thing.
    expect(rendered.match(/Not available yet/g)).toHaveLength(2);
  });

  it("invents no content for either", () => {
    // Placeholder items would be the platform implying information it does not
    // have, which CLAUDE.md §15 forbids in its strongest terms.
    const rendered = text(render());

    expect(rendered).not.toContain("Unread");
    expect(rendered).not.toContain("Suggested");
  });
});

describe("the single-workspace disclosure", () => {
  it("states the limitation when the user belongs to more workspaces", () => {
    const rendered = text(render({ otherWorkspaceCount: 2 }));

    expect(rendered).toContain("2 other workspaces");
    expect(rendered).toContain("switching between them is not available yet");
  });

  it("says nothing about switching when there is only one workspace", () => {
    const rendered = text(render({ otherWorkspaceCount: 0 }));

    expect(rendered).not.toContain("switching between them");
  });

  it("writes one other workspace in the singular", () => {
    const rendered = text(render({ otherWorkspaceCount: 1 }));

    expect(rendered).toContain("1 other workspace ");
  });
});
