---
title: STEP-24 Dashboard
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-14
tags: [engineering, workflow, build-step, frontend]
step_id: STEP-24
step_status: Not Started
detail_level: full
---

# STEP-24 — Dashboard

**Status:** Not Started
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

Render the most recent projects, newest first, each linking to its own project page, reusing the existing status presentation rather than inventing a second one. Empty state: a short line explaining that projects appear here once created, with the link to `/projects`.

### 4. Active workflows section

Render runs whose status is `awaiting_approval`, `running` or `pending`, **ranked in that order**. `awaiting_approval` sorts first because it is the only one of the three that is blocked on the user — it is literally what "needs attention" means, and surfacing it is most of this page's purpose.

Each entry shows its workflow type, its status, and when it started. Completed and failed runs are not active and are not listed here. Empty state: a short line stating that no workflows are currently running.

### 5. AI budget glance

A **minimal read-only** summary drawn from the budgets already returned by `listBudgets`: spend against the current period's USD ceiling, and a clearly visible warning when a budget's circuit breaker is open. It links to [[Settings]] for the detail.

This is a glance, not a report. It does not duplicate the spend summary that `/settings` already renders, does not list spend records, and does not add a chart. An open circuit breaker means AI work is being refused right now — that is the single highest-value "needs attention" signal the platform currently has, which is why it belongs on the home surface while the rest of the spend detail does not.

Amounts render as the decimal strings the API returns.

### 6. Quick actions

Links to the surfaces that exist in this build. An action whose destination does not exist is not rendered as a disabled or dead control — a control that cannot act is a dark pattern (CLAUDE.md §35), and the [[Dashboard]] specification's full action list describes the finished product, not this step.

### 7. Stub sections

Notifications and AI recommendations render as clearly labelled "Not available yet" states. They are neither omitted nor filled with placeholder content that could be mistaken for real data — the platform does not imply information it does not have (CLAUDE.md §15).

### 8. Loading, error and empty states

Add `loading.tsx` with a skeleton whose shape mirrors the real dashboard layout, and `error.tsx` as a route-scoped Client Component boundary. Every section defines its own empty state; the page does not collapse to a single page-level empty state, because "no projects yet" and "no workflows running" are different facts and a user needs to tell them apart.

### 9. Accessibility and design system compliance

Each section is a labelled landmark with an accessible name tied to its heading. Every interactive element is keyboard reachable with a visible focus state. Skeletons carry a status role, a busy attribute and a screen-reader-only label; the error boundary carries an alert role. Semantic tokens only, no new UI patterns.

### 10. Disclose the single-workspace limitation

The dashboard reports on one workspace. Say so in the interface, consistent with how `/projects` and `/settings` already handle it.

### 11. Tests

Unit tests for the new client function covering the success path and the error path, mirroring the existing API client tests. Tests for the presentational component covering the active-run filter and its ranking order, the breaker-open warning, and each empty state.

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
- **The error boundary is observed** to render without exposing the raw error message or a stack trace.
- **Every required CI check on the Pull Request is green.**

### Where each was proven

Recorded at completion: which command, which test, or which manual check established each line above. A validation claim with no stated evidence is an assumption.

## Manual Browser Test Checklist

- [ ] `/dashboard` loads for an authenticated user with a workspace.
- [ ] Recent projects list real projects, newest first, and each link opens the right project.
- [ ] Active workflows show only `awaiting_approval`, `running` and `pending` runs, with `awaiting_approval` first.
- [ ] Completed and failed runs do not appear in the active list.
- [ ] The AI budget glance shows spend against the ceiling, and its link reaches the Settings spend detail.
- [ ] With a budget's circuit breaker open, the warning is visible without scrolling or interaction.
- [ ] Notifications and AI recommendations read as clearly labelled "Not available yet", not as empty or broken sections.
- [ ] Every quick action leads to a working surface. No dead or disabled controls.
- [ ] A user with no workspace sees the no-workspace state, not an error.
- [ ] A workspace with no projects and no runs shows per-section empty states, each distinguishable from the others.
- [ ] The loading skeleton matches the real layout closely enough that content does not visibly jump when it resolves.
- [ ] Forcing a data failure renders the route-scoped error boundary; the shell and navigation survive; no raw error message or stack trace is shown; retry works.
- [ ] The whole page is keyboard navigable, with a visible focus indicator on every interactive element and a sensible tab order.
- [ ] The single-workspace limitation is disclosed in the interface.
- [ ] **Timed 30-second check** — with seeded, realistic data (several projects, at least one run awaiting approval), a returning user opens `/dashboard`, states what needs attention, and reaches a working surface. **Timed with a stopwatch and the result recorded in this note.** Under 30 seconds passes; over 30 seconds fails and the layout is revised before this step is `Done`. This is the [[Dashboard]] success criterion, and the Scope section requires it be validated rather than assumed.

## Definition of Done

- [ ] The dashboard renders recent projects, active workflows and quick actions against real data.
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
