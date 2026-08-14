import type { Metadata } from "next";
import Link from "next/link";

import { StatusBadge } from "@/components/projects/StatusBadge";
import { EmptyState } from "@/components/shell/EmptyState";
import {
  type ApiBudget,
  type ApiProject,
  type ApiWorkflowRun,
  listBudgets,
  listProjects,
  listWorkflowRuns,
} from "@/lib/api";
import { requireProfile, resolveAccessToken } from "@/lib/auth";
import {
  activeRuns,
  hasOpenBreaker,
  recentProjects,
  runTimestamp,
  workspaceBudget,
} from "@/lib/dashboard";
import { resolveWorkspace } from "@/lib/workspace";

export const metadata: Metadata = {
  title: "Dashboard — ProjectOne",
};

/**
 * The home surface: what needs attention, and the way back into work.
 *
 * A **Server Component**, following the pattern `/projects` and `/settings`
 * settled: the access token lives in an httpOnly cookie the browser cannot read,
 * so every value here is fetched server-side and passed down as props. Nothing
 * on this page needs browser state, an event handler or an effect, so no part of
 * it becomes a Client Component (CLAUDE.md §11).
 *
 * ## What this page is not
 *
 * It is a **summary**, not a fourth copy of the list screens. Each section caps
 * its rows and links to the surface that holds the rest. The [[Dashboard]]
 * specification's fuller component list — notifications, upcoming publications,
 * analytics, AI recommendations — describes the finished product; the domains
 * feeding most of it do not exist yet, and the two this step is asked to show
 * anyway are rendered as honest "not available" states rather than as invented
 * content (CLAUDE.md §15).
 *
 * ## The three fetches are parallel
 *
 * They are independent, so awaiting them in sequence would add their latencies
 * together for no benefit — the same reasoning `/settings` records for its four.
 */
export default async function DashboardPage() {
  await requireProfile();

  const accessToken = await resolveAccessToken();
  const workspace = accessToken === undefined ? undefined : await resolveWorkspace(accessToken);

  if (accessToken === undefined || workspace === undefined) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Dashboard</h1>
        <EmptyState
          title="No workspace yet"
          description="Your work lives inside a workspace. Once you belong to one, what needs attention appears here."
        />
      </div>
    );
  }

  const workspaceId = workspace.current.id;

  const [projects, runs, budgets] = await Promise.all([
    listProjects(accessToken, workspaceId),
    listWorkflowRuns(accessToken, workspaceId),
    listBudgets(accessToken, workspaceId),
  ]);

  return (
    <DashboardScreen
      workspaceName={workspace.current.name}
      otherWorkspaceCount={workspace.available.length - 1}
      projects={projects}
      runs={runs}
      budgets={budgets}
    />
  );
}

interface DashboardScreenProps {
  readonly workspaceName: string;
  readonly otherWorkspaceCount: number;
  readonly projects: readonly ApiProject[];
  readonly runs: readonly ApiWorkflowRun[];
  readonly budgets: readonly ApiBudget[];
}

/**
 * The rendered screen, separated from the data fetching above it.
 *
 * The same split `/projects` and `/settings` use: the layout is readable without
 * the awaits, and the selection rules it calls are asserted directly in
 * `lib/dashboard.test.ts` rather than through a rendered tree.
 */
function DashboardScreen({
  workspaceName,
  otherWorkspaceCount,
  projects,
  runs,
  budgets,
}: DashboardScreenProps) {
  const shownProjects = recentProjects(projects);
  const shownRuns = activeRuns(runs);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight text-text">Dashboard</h1>
        <p className="text-sm text-text-muted">
          What needs attention in {workspaceName}.
          {/*
           * The multi-workspace limitation, disclosed rather than hidden — the
           * application resolves the caller's first workspace and has no
           * switcher. Stated the same way `/projects` and `/settings` state it.
           */}
          {otherWorkspaceCount > 0
            ? ` You belong to ${otherWorkspaceCount} other ${
                otherWorkspaceCount === 1 ? "workspace" : "workspaces"
              } — switching between them is not available yet.`
            : ""}
        </p>
      </div>

      <BudgetGlance budgets={budgets} />

      <ActiveWorkflows runs={shownRuns} />

      <RecentProjects projects={shownProjects} />

      <QuickActions />

      <StubSections />
    </div>
  );
}

/**
 * A section heading and its body, sharing one accessible name.
 *
 * Every section is a landmark labelled by its own heading, so a screen reader
 * user can move between them rather than reading the page top to bottom.
 */
function Section({
  id,
  title,
  action,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly action?: React.ReactNode;
  readonly children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={`${id}-heading`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={`${id}-heading`} className="text-lg font-medium text-text">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A link to the surface holding everything a capped section omits. */
function SectionLink({ href, children }: { readonly href: string; readonly children: string }) {
  return (
    <Link
      href={href}
      className="rounded-sm text-sm text-accent underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      {children}
    </Link>
  );
}

/**
 * Spend against the workspace-wide ceiling, and whether AI work is paused.
 *
 * ## Two independent questions
 *
 * "How much of the ceiling is left" is answered by the workspace-wide budget
 * alone — never by summing budgets, which would count the same spend twice (see
 * `workspaceBudget`). "Is anything paused" is answered by *any* budget's
 * breaker, because a tripped per-workflow breaker refuses work whether or not a
 * workspace-wide budget exists.
 *
 * They are rendered separately because they can disagree: a workspace with no
 * workspace-wide budget can still have a per-workflow breaker open, and the
 * warning has to appear anyway.
 *
 * Amounts render as the decimal strings the API returns. Parsing money to a
 * float and formatting it back is how a displayed figure stops matching the
 * ledger it came from.
 */
function BudgetGlance({ budgets }: { readonly budgets: readonly ApiBudget[] }) {
  const budget = workspaceBudget(budgets);
  const breakerOpen = hasOpenBreaker(budgets);

  return (
    <Section id="ai-spend" title="AI spend" action={<SectionLink href="/settings">Manage</SectionLink>}>
      {breakerOpen ? (
        <p
          role="status"
          className="rounded-md border border-danger bg-surface px-4 py-3 text-sm text-danger"
        >
          One or more AI workflows are paused by a spending limit. Review your budgets in{" "}
          <Link href="/settings" className="underline underline-offset-4">
            Settings
          </Link>
          .
        </p>
      ) : null}

      {budget === undefined ? (
        <p className="rounded-lg border border-border bg-surface px-6 py-5 text-sm text-text-muted">
          No workspace-wide AI budget configured.{" "}
          <Link
            href="/settings"
            className="text-accent underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Set one in Settings
          </Link>{" "}
          to cap what AI work can cost.
        </p>
      ) : (
        <div className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg border border-border bg-surface px-6 py-5">
          <p className="text-sm text-text">Spent this period</p>
          <p className="font-mono text-sm text-text-muted">
            ${budget.spent_usd} of ${budget.limit_usd}
          </p>
        </div>
      )}
    </Section>
  );
}

/**
 * Runs that are waiting, running, or blocked on an approval.
 *
 * **Nothing here links anywhere.** There is no workflow route in the
 * application, and inventing one so a row could be clickable would be a
 * speculative route built for a surface that does not exist. A later step that
 * adds a workflow screen adds the link then.
 */
function ActiveWorkflows({ runs }: { readonly runs: readonly ApiWorkflowRun[] }) {
  return (
    <Section id="active-workflows" title="Active workflows">
      {runs.length === 0 ? (
        <EmptyState
          title="No workflows running"
          description="Workflows you start appear here while they run, and stay if one needs your approval."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {runs.map((run) => (
            <li key={run.id}>
              <WorkflowRow run={run} />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/** How each active state is written in the interface. */
const RUN_STATUS_LABELS: Record<"pending" | "running" | "awaiting_approval", string> = {
  awaiting_approval: "Awaiting approval",
  running: "Running",
  pending: "Queued",
};

function WorkflowRow({ run }: { readonly run: ApiWorkflowRun }) {
  const timestamp = runTimestamp(run);
  const awaiting = run.status === "awaiting_approval";
  const label =
    run.status === "awaiting_approval" || run.status === "running" || run.status === "pending"
      ? RUN_STATUS_LABELS[run.status]
      : run.status;

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border bg-surface px-6 py-5">
      <div className="flex flex-col gap-1">
        <span className="text-base font-medium text-text">{run.workflow_type}</span>
        <span className="text-sm text-text-muted">
          {timestamp.label} <time dateTime={timestamp.at}>{timestamp.at}</time>
        </span>
      </div>

      {/*
       * Only the blocked state is emphasized. Colouring all three would be three
       * colour decisions carrying no information, the same reasoning
       * `StatusBadge` records — and the one that needs a human is the one worth
       * distinguishing.
       */}
      <span
        className={[
          "inline-flex shrink-0 items-center rounded-full border px-3 py-1 text-xs font-medium",
          awaiting ? "border-accent text-accent" : "border-border text-text-muted",
        ].join(" ")}
      >
        {label}
      </span>
    </div>
  );
}

/** The newest projects, capped, with the route to the rest. */
function RecentProjects({ projects }: { readonly projects: readonly ApiProject[] }) {
  return (
    <Section
      id="recent-projects"
      title="Recent projects"
      action={<SectionLink href="/projects">All projects</SectionLink>}
    >
      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet"
          description="Projects group your scripts, media and published work."
          action={<SectionLink href="/projects">Create your first project</SectionLink>}
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {projects.map((project) => (
            <li key={project.id}>
              <Link
                href={`/projects/${project.id}`}
                className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border bg-surface px-6 py-5 transition-colors hover:bg-surface-raised"
              >
                <span className="text-base font-medium text-text">{project.name}</span>
                <StatusBadge status={project.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/**
 * The ways back into work.
 *
 * Three, because three surfaces exist. The [[Dashboard]] specification also
 * names Create Project, Upload Files, Review Approvals and View Analytics —
 * none of which has a destination in this build, and Analytics is Phase 2
 * entirely. Rendering them as disabled controls would be a menu of things that
 * do not work, which is the dark pattern CLAUDE.md §35 forbids rather than a
 * preview of the roadmap.
 */
function QuickActions() {
  const actions: readonly { readonly href: string; readonly label: string }[] = [
    { href: "/projects", label: "Projects" },
    { href: "/chat", label: "AI Chat" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <Section id="quick-actions" title="Quick actions">
      <ul className="flex flex-wrap gap-3">
        {actions.map((action) => (
          <li key={action.href}>
            <Link
              href={action.href}
              className="inline-flex items-center rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text transition-colors hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {action.label}
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/**
 * The two sections the [[Dashboard]] specification names whose domains do not
 * exist yet.
 *
 * Stated plainly rather than omitted or filled with plausible-looking content.
 * Omitting them would hide a known gap from the person deciding what to build
 * next; inventing content would be the platform implying information it does not
 * have, which CLAUDE.md §15 forbids in the strongest terms it uses.
 */
function StubSections() {
  return (
    <div className="grid gap-6 sm:grid-cols-2">
      <Section id="notifications" title="Notifications">
        <p className="rounded-lg border border-border border-dashed bg-surface px-6 py-5 text-sm text-text-muted">
          Not available yet. Notifications arrive with the domains that raise them.
        </p>
      </Section>

      <Section id="recommendations" title="AI recommendations">
        <p className="rounded-lg border border-border border-dashed bg-surface px-6 py-5 text-sm text-text-muted">
          Not available yet. Recommendations need more of your activity than the platform records
          today.
        </p>
      </Section>
    </div>
  );
}
