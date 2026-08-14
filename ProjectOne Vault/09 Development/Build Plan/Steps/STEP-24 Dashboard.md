---
title: STEP-24 Dashboard
category: Development/Build Step
status: draft
version: "2.1"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-24
step_status: In Progress
detail_level: full
---

# STEP-24 — Dashboard

**Status:** In Progress
**Detail level:** full — expanded by [[STEP-23 AI Chat End to End]], per [[Execution Protocol]].

## Goal

The home surface: recent projects, active workflows, quick actions — closing the Foundation loop.

## Scope

Notifications, cost summary and AI recommendations are stubbed until the domains feeding them exist. The [[Dashboard]] success criterion is literal and must be **validated, not assumed**: a returning user understands what needs attention and starts meaningful work in under 30 seconds.

## Prerequisites

- [[STEP-23 AI Chat End to End]] — `Done`

## Required Documentation

- [[Dashboard]]
- [[Design System]]

**Reference only, not required reading:** [[Design Backlog and UI Vision]] holds a Dashboard concept mockup and a target component list (AI Provider Status Bar, KPI cards, spend overview, activity timeline, active queue, system health, usage by model, command palette). It is **informational and binds nothing** — this step delivers the [[Dashboard]] specification against [[Design System]], at the scope in this note's own Scope section, and is not measured against that mockup. Several elements it depicts have no build step at all. Improvements noticed here are collected in [[Design Backlog and UI Vision#UI Polish Backlog]], not built.

## Inherited from STEP-23

Facts about the code as it stands, established by the steps before this one. They are recorded here so this step reuses what exists instead of rediscovering or duplicating it.

- **The app shell, its routes and its navigation already exist.** `/dashboard` is a real, navigable segment holding a placeholder. This step replaces that placeholder's content; it does not restructure the segment, the shell or the navigation.
- **The authenticated Server Component pattern is settled.** A page resolves the viewer with `requireProfile()`, then `resolveAccessToken()`, then `resolveWorkspace(accessToken)`, and renders an `EmptyState` when the viewer has no workspace. `/projects` and `/settings` both follow it and are the reference implementations.
- **Data fetching is parallel, in the page, above the presentational component.** `/settings` fetches four resources in one `Promise.all` deliberately: sequential awaits multiply latency for no benefit when the calls are independent.
- **Pages split fetching from rendering.** An `async` page component fetches and passes `readonly` props to a plain presentational component. This keeps the rendering testable without a live API.
- **The projects client function exists.** `listProjects(accessToken, workspaceId)` ships and is what "recent projects" reads.
- **The workflow runs endpoint exists; its web client does not.** `GET /workspaces/{workspace_id}/workflows/runs` returns recent runs newest-first, each with its steps, bounded by the repository's own limit. The web app has no workflow client function at all. This step adds one — consuming an existing contract, not changing it.
- **AI spend and budgets are already exposed and already consumed.** `listBudgets` and `listSpendRecords` ship, and `/settings` renders the full spend summary from them under its AI Spend section. That page remains the home of spend detail; this step does not duplicate it.
- **Money is carried as decimal strings end to end.** Amounts arriving from the API are strings and are rendered as strings. They are never parsed into a JavaScript `number` — floating point is exactly the wrong representation for currency.
- **Loading and error states are route-scoped files.** `loading.tsx` renders a skeleton whose shape mirrors the real content, because a mismatched skeleton causes the reflow it exists to prevent ([[Design System]] §10). `error.tsx` is a Client Component scoped inside the shell, so a failure in one route does not take down the surrounding application.
- **Errors never leak internals.** An error boundary renders a human message and the error digest as a support reference. It never renders the raw error message or a stack trace (CLAUDE.md §24).
- **Styling is semantic tokens only.** `text-text`, `bg-surface`, `border-border`, `bg-skeleton`, `text-accent`. No dark-mode variants, no raw palette values, no inline styles except for genuinely dynamic values.
- **There is no workspace switcher yet.** Pages that depend on a single active workspace say so in the interface rather than implying a choice the user does not have. `/projects` and `/settings` both disclose this.

## Tasks

### 1. Add the workflow runs client function

Add `listWorkflowRuns(accessToken, workspaceId)` and its response types to the web API client, alongside the existing project, conversation and spend functions. It calls the existing `GET /workspaces/{workspace_id}/workflows/runs` endpoint.

Types mirror the API's own response schema exactly — run identity, workflow type, status, project reference, detail, who triggered it and the timestamps, plus the nested steps with their index, name, status, detail, tokens used and timestamps. All fields `readonly`, no `any`, and no invented fields: if the endpoint does not return it, the type does not declare it.

This is implementation support for the already-approved "active workflows" scope. It adds no endpoint, no route and no API change.

### 2. Build the dashboard page

Replace the `/dashboard` placeholder with a Server Component following the settled pattern: resolve the viewer, resolve the workspace, render the no-workspace empty state when there is none, then fetch the page's data in a single parallel batch — projects, workflow runs and budgets — and pass it to a presentational dashboard component.

That component takes `readonly` props and performs no data fetching of its own. It stays a Server Component: nothing on this page needs browser state, event handlers or effects.

### 3. Recent projects section

Render **at most 5** projects, **preserving the order the API already returns** (newest first). The client does not re-sort: the ordering is the server's, and a second sort in the client is a copy of a rule that will drift from it.

Each project links to its own project page, reusing the existing status presentation rather than inventing a second one. The section includes a link to `/projects` for the full list — the cap is what makes this a summary, so the route to everything it omits has to be present.

Empty state: a short line explaining that projects appear here once created, with the link to `/projects`.

### 4. Active workflows section

Render runs whose status is `awaiting_approval`, `running` or `pending`, **ranked in that order**, and **within a single status, newest first**. Show **at most 5 after filtering** — the cap applies to the filtered, ranked list, so the five shown are the five most deserving of attention, not the first five that happened to come back.

`awaiting_approval` sorts first because it is the only one of the three that is blocked on the user — it is literally what "needs attention" means, and surfacing it is most of this page's purpose.

Each entry shows its workflow type, its status, and its timestamp per Task 4a. Completed and failed runs are not active and are not listed here.

**No link to a workflow destination.** There is no workflow route in the web application today — `/chat`, `/projects`, `/projects/[projectId]`, `/settings` and `/dashboard` are the entire authenticated surface. This step does not invent one. If a workflow surface is added by a later step, adding the link here is that step's work, not a route created speculatively by this one.

Empty state: a short line stating that no workflows are currently running.

### 4a. Workflow timestamp

`started_at` is nullable on the API's run response; `created_at` is not. A pending run has not started, so its `started_at` is absent by design.

- When `started_at` is present, show it, labelled as **started**.
- When it is absent, show `created_at`, labelled as **created** or **queued**.

The label always matches the field being shown. Rendering a creation time under a "started" label states something untrue about a run that has not begun — and for a queue of pending work, "how long has this been waiting" is precisely the question the timestamp exists to answer.

### 5. AI budget glance

A **minimal read-only** summary drawn from the budgets already returned by `listBudgets`. It links to [[Settings]] for the detail.

**Spend versus ceiling uses the workspace-wide budget — the one whose `workflow_type` is `null` — and only that one.** The returned list mixes the workspace-wide budget with per-workflow-type budgets that draw against the same spend. Summing them would count the same dollars more than once and report a number that is simply wrong, so this line reads exactly one budget rather than aggregating.

**When no workspace-wide budget exists**, render an honest "No workspace-wide AI budget configured" state linking to Settings. It does not fall back to a per-workflow budget and present it as though it covered the workspace, and it does not render a zero that would read as "nothing spent."

**The breaker warning is separate from that line.** Show a warning when **any** returned budget has `breaker_open` set — a tripped per-workflow breaker is refusing work right now whether or not a workspace-wide budget is configured. The warning says that AI work is being blocked and points to Settings; it does not surface `breaker_reason` or other internal breaker state on this page, because a home surface needs to convey that something is wrong and where to go, not the diagnostic detail.

This is a glance, not a report. It does not duplicate the spend summary that `/settings` already renders, does not list spend records, and does not add a chart. An open circuit breaker means AI work is being refused right now — that is the single highest-value "needs attention" signal the platform currently has, which is why it belongs on the home surface while the rest of the spend detail does not.

Amounts render as the decimal strings the API returns.

### 6. Quick actions

Exactly three, each to a route that exists today:

- **Projects** → `/projects`
- **AI Chat** → `/chat`
- **Settings** → `/settings`

No create, upload, approval or other action is added. The [[Dashboard]] specification's fuller action list (Create Project, Upload Files, Review Approvals, View Analytics) describes the finished product, not this step — those destinations do not exist in this build, and Analytics is Phase 2 and out of the Build Plan's scope entirely.

An action whose destination does not exist is not rendered as a disabled or dead control — a control that cannot act is a dark pattern (CLAUDE.md §35).

### 7. Stub sections

Notifications and AI recommendations render as clearly labelled "Not available yet" states. They are neither omitted nor filled with placeholder content that could be mistaken for real data — the platform does not imply information it does not have (CLAUDE.md §15).

### 8. Loading, error and empty states

Add `loading.tsx` with a skeleton whose shape mirrors the real dashboard layout, and `error.tsx` as a route-scoped Client Component boundary. Every section defines its own empty state; the page does not collapse to a single page-level empty state, because "no projects yet" and "no workflows running" are different facts and a user needs to tell them apart.

### 9. Accessibility and design system compliance

Each section is a labelled landmark with an accessible name tied to its heading. Every interactive element is keyboard reachable with a visible focus state. Skeletons carry a status role, a busy attribute and a screen-reader-only label; the error boundary carries an alert role. Semantic tokens only, no new UI patterns.

### 10. Disclose the single-workspace limitation

The dashboard reports on one workspace. Say so in the interface, consistent with how `/projects` and `/settings` already handle it.

### 11. Tests

Unit tests for the new client function covering the success path and the error path, mirroring the existing API client tests.

Tests for the presentational component covering each rule that can silently regress:

- Recent projects cap at 5, and the API's ordering is preserved rather than re-sorted.
- Active workflows exclude completed and failed runs.
- Status ranking is `awaiting_approval`, then `running`, then `pending`.
- Within one status, newest first.
- The cap of 5 applies after filtering and ranking, not before.
- Timestamps: `started_at` renders labelled as started; a pending run with no `started_at` renders `created_at` labelled as created or queued.
- The budget line reads the `workflow_type === null` budget and does not sum budgets — a fixture with a workspace-wide budget plus per-workflow budgets must not produce their total.
- The no-workspace-wide-budget state renders when no such budget is present.
- The breaker warning renders when any budget has `breaker_open` set, including when the tripped budget is a per-workflow one, and does not render `breaker_reason`.
- Each empty state renders.

### 12. Documentation

Update [[Dashboard]] to record what this step actually delivered and what remains stubbed, so the feature note does not describe behaviour the product does not have. Mark this step `Done` in both this note and the [[Build Plan]] index, and expand [[STEP-25 Launch Readiness Criteria]] to full detail, per [[Execution Protocol]].

## Validation

Observed, not assumed. A type-check alone is not validation.

- **Type-check and lint pass** across the web application.
- **Unit tests pass**, including the new client-function and component tests.
- **The full test suite passes** — this step must not regress STEP-22 or STEP-23 behaviour.
- **The page renders against a running API** with a real workspace: projects, active workflows and the budget glance each show real data.
- **Each empty state is observed**, not inferred — a workspace with no projects and no runs renders the empty sections correctly.
- **The breaker warning is observed** in the state where a budget's circuit breaker is open.
- **No route was added.** The application's route list is unchanged by this step: `/dashboard`, `/chat`, `/projects`, `/projects/[projectId]`, `/settings` and the auth routes, exactly as before. Every link this page renders points at one of them.
- **The error boundary is observed** to render without exposing the raw error message or a stack trace.
- **Every required CI check on the Pull Request is green.**

### Where each was proven

Recorded at completion: which command, which test, or which manual check established each line above. A validation claim with no stated evidence is an assumption.

## Manual Browser Test Checklist

- [ ] `/dashboard` loads for an authenticated user with a workspace.
- [ ] Recent projects list real projects, newest first, capped at 5, and each link opens the right project.
- [ ] With more than 5 projects in the workspace, exactly 5 appear and the link to `/projects` reaches the full list.
- [ ] Active workflows show only `awaiting_approval`, `running` and `pending` runs, with `awaiting_approval` first, then `running`, then `pending`.
- [ ] Within one status, the newest run appears first.
- [ ] With more than 5 active runs, exactly 5 appear, and they are the highest-ranked 5 rather than an arbitrary 5.
- [ ] Completed and failed runs do not appear in the active list.
- [ ] A running run shows its start time labelled as started; a pending run with no start time shows its creation time labelled as created or queued.
- [ ] The AI budget glance shows spend against the workspace-wide ceiling, and its link reaches the Settings spend detail.
- [ ] With a workspace-wide budget **and** per-workflow budgets configured, the figure shown matches the workspace-wide budget alone and is not their sum.
- [ ] With no workspace-wide budget configured, the honest "not configured" state renders and links to Settings.
- [ ] With a budget's circuit breaker open, the warning is visible without scrolling or interaction, including when only a per-workflow budget has tripped.
- [ ] The breaker warning does not display internal breaker reason text.
- [ ] Notifications and AI recommendations read as clearly labelled "Not available yet", not as empty or broken sections.
- [ ] Exactly three quick actions render — Projects, AI Chat, Settings — and each opens its surface. No dead or disabled controls, and no action without an existing destination.
- [ ] No workflow entry links anywhere, since no workflow route exists.
- [ ] A user with no workspace sees the no-workspace state, not an error.
- [ ] A workspace with no projects and no runs shows per-section empty states, each distinguishable from the others.
- [ ] The loading skeleton matches the real layout closely enough that content does not visibly jump when it resolves.
- [ ] Forcing a data failure renders the route-scoped error boundary; the shell and navigation survive; no raw error message or stack trace is shown; retry works.
- [ ] The whole page is keyboard navigable, with a visible focus indicator on every interactive element and a sensible tab order.
- [ ] The single-workspace limitation is disclosed in the interface.
- [ ] **Timed 30-second check** — with seeded, realistic data (several projects, at least one run awaiting approval), a returning user opens `/dashboard`, states what needs attention, and reaches a working surface. **Timed with a stopwatch and the result recorded in this note.** Under 30 seconds passes; over 30 seconds fails and the layout is revised before this step is `Done`. This is the [[Dashboard]] success criterion, and the Scope section requires it be validated rather than assumed.

## Definition of Done

- [ ] The dashboard renders recent projects, active workflows and quick actions against real data.
- [ ] Both lists are capped at 5, with the workflow cap applied after filtering and ranking.
- [ ] No route was added, and no link points at a destination that does not exist.
- [ ] The AI budget glance reads the workspace-wide budget only, never a sum, and renders the honest "not configured" state when there is none.
- [ ] The AI budget glance is present, read-only, and links to Settings without duplicating its spend detail.
- [ ] Notifications and AI recommendations are honest, labelled stubs.
- [ ] Loading, error and empty states exist for the route and for every section.
- [ ] Accessibility requirements are met and observed.
- [ ] [[Design System]] is followed exactly; no new UI patterns were invented.
- [ ] No `any`, no unvalidated external input, no secrets in client code.
- [ ] Tests cover the new client function and the component's filtering, ranking and warning behaviour.
- [ ] Every Validation line above passes, with its evidence recorded.
- [ ] The manual checklist is complete, **including the timed 30-second check**.
- [ ] [[Dashboard]] is updated to match what shipped.
- [ ] Every required CI check on the Pull Request is green.
- [ ] Every review conversation is resolved.
- [ ] [[STEP-25 Launch Readiness Criteria]] is expanded to full detail.
- [ ] Status is `Done` in this note **and** in the [[Build Plan]] index, and the two agree.

### Completion state

This step is **not Critical** under CLAUDE.md §21: it changes no database schema, no authentication or authorization boundary, no multi-tenancy or RLS policy, no billing logic, no infrastructure, no AI or agent architecture, and no public API contract. It consumes existing endpoints and adds frontend surface only.

This step stays `In Progress` until every box above is checked. `Done` is claimed after the checks, never before — marking it earlier claims a verification that has not happened.

---

## Navigation

- **Previous:** [[STEP-23 AI Chat End to End]]
- **Next:** [[STEP-25 Launch Readiness Criteria]]
- **Parent:** [[Build Plan]]
