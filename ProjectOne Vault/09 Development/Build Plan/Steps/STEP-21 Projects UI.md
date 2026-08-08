---
title: STEP-21 Projects UI
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, frontend, backend]
step_id: STEP-21
step_status: Not Started
detail_level: full
---

# STEP-21 — Projects UI

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-20 Projects Schema and Lifecycle]], per [[Execution Protocol]].

## Goal

Create projects, organize assets, and move a project through its lifecycle — the core workspace surface, reachable by a real user.

## Scope

**Endpoints *and* UI.** [[STEP-20 Projects Schema and Lifecycle]] deliberately built no HTTP layer (owner decision, 2026-08-08: its Tasks named a migration, repositories, a service and tests, and nothing else), so the `/api/v1/projects` routes are this step's work rather than inherited.

Workspace-isolated and RLS-verified through the UI path, not only at the database.

**Out of scope:** generation, publishing and analytics surfaces; asset *upload* (no storage backend exists — see below); a workspace switcher.

## Prerequisites

- [[STEP-20 Projects Schema and Lifecycle]] — `Done`, and owner-approved (it carries an approval gate)

## Required Documentation

- [[Project Lifecycle]] — the transition rules this UI must not reimplement
- [[API Endpoints]] — the contract every new route joins
- [[Design System]] — the UI standard, which wins over [[Design Backlog and UI Vision]] wherever they differ
- [[Web Session Handling]] — how a server-side call reaches the API

**Reference only, not required reading:** [[Design Backlog and UI Vision]]. It binds nothing and must not change what this step builds.

## Inherited from STEP-20

Recorded during expansion, while the context was loaded. These are the load-bearing facts, not a substitute for reading the notes.

- **The service exists and owns the state machine.** `ProjectService` (`app/services/project_service.py`) provides `create`, `get`, `list_for_workspace`, `transition`, `rename`, `archive`, `delete`, `add_asset`, `list_assets`, `delete_asset`. A router calls these; it does not re-decide anything.
- **`legal_transitions_from(status)` exists and is public specifically for this step.** The UI must offer exactly those states and **must not reimplement the rules in TypeScript** — two copies of a state machine diverge. Expose it through the API rather than hardcoding a map in the frontend.
- **Two error types need HTTP handlers**, and neither has one yet: `ProjectNotFoundError` → **404**, `IllegalTransitionError` → **409** (a conflict with current state, not a validation error — the request is well-formed and the value is in the vocabulary). Translation belongs in `app/core/errors.py`'s handler table, never in a router ([[API Conventions]]).
- **`IllegalTransitionError.public_message` names both states and is safe to show.** `ProjectNotFoundError` deliberately conflates "absent" with "hidden by RLS" — do not add a message distinguishing them.
- **Any live member may create and edit a project**, unlike the owner/admin gate on AI settings. If a route needs `requires(...)`, it is `VIEW_WORKSPACE`; there is no project-specific permission in `app/core/permissions.py` and adding one is a decision, not a detail.
- **Archive ≠ delete.** Archive is a lifecycle state; delete is soft deletion. The UI must not present one as the other — see [[Project Lifecycle#Archive Is Not Deletion]].
- **Asset upload has no backend.** `assets.storage_path` is an opaque locator pointing at nothing; no storage service is chosen. A step that adds one also owes it a deletion path ([[CLAUDE|CLAUDE.md]] §16). **Do not choose a storage backend here** — that is an ADR ([[CLAUDE|CLAUDE.md]] §10/§28), not a detail of a UI step.
- **The web app still resolves the caller's *first* workspace** (`lib/workspace.ts`) and has no switcher. A projects list is workspace-scoped, so it inherits that constraint and must state it on screen as STEP-19's settings screens do.
- **`POST /api/v1/projects` is a resource-creating route with no idempotency key**, like `POST /workspaces` before it. Still unbuilt and still recorded rather than forgotten.

## Tasks

1. **Schemas** — `app/schemas/project.py`: request and response models. `extra="forbid"` on every request model, as STEP-19 established, so an unexpected field is a 422 rather than a silent discard. A response carries the project's legal next states so the UI need not derive them.
2. **Router** — `app/routers/projects.py`: list, create, read, rename, transition, delete; list and add assets, delete an asset. Routes validate and call the service, nothing else ([[CLAUDE|CLAUDE.md]] §12). Register on `/api/v1`.
3. **Error handlers** — map `ProjectNotFoundError` → 404 and `IllegalTransitionError` → 409 in `app/core/errors.py`, so both reach the client inside the standard envelope.
4. **Dependencies** — wire `ProjectService` over `TenantConnectionDep` in `app/core/dependencies.py`, following the `ProviderCredentialService` precedent.
5. **UI** — a projects list, a create form, and a project detail view showing status, legal transitions and assets. Each with a loading skeleton, an empty state and a route-scoped error boundary, per [[Design System]] and STEP-19's shape.
6. **Rate limiting** — `POST /api/v1/projects` carries a per-user limit on its own merits, as `POST /workspaces` does ([[STEP-12a Trusted Proxy and Per-User Rate Limiting]]).

## Validation

- **An illegal transition returns 409 through HTTP**, and a legal one returns the updated project — both halves, through the real route rather than the service.
- **A member of another workspace gets 404, not 403**, for a project they cannot see — proving the RLS path and the error conflation together.
- **The UI offers exactly `legal_transitions_from`'s states** for a project in each of several states, asserted rather than eyeballed.
- **No route can return another tenant's project**, proven against real response bodies.
- Every new screen renders its loading, empty and error states.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

Projects and assets are reachable over HTTP and manageable from the UI, lifecycle transitions are enforced end to end with an illegal one refused as 409, isolation is proven through the route layer, and every new screen defines loading, empty and error states.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — public API contract, multi-tenancy) and carries an **owner approval gate**.

---

## Navigation

- **Previous:** [[STEP-20 Projects Schema and Lifecycle]]
- **Next:** [[STEP-22 Minimum Workflow Engine]]
- **Parent:** [[Build Plan]]
