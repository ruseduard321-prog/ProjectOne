---
title: STEP-21 Projects UI
category: Development/Build Step
status: stable
version: "3.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, frontend, backend]
step_id: STEP-21
step_status: Done
detail_level: full
---

# STEP-21 — Projects UI

**Status:** Done
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

## Outcome

Nine routes, six Server Actions, three screens and 50 new tests (34 API, 16 web). Projects are reachable end to end: a real user creates one, moves it through the lifecycle, attaches assets and deletes it, and no route can return another tenant's work.

### What was built

**API** — `app/schemas/project.py`, `app/routers/projects.py`, plus `ProjectRepository`/`ProjectService` wiring in `app/core/dependencies.py` and two new handlers in `app/core/errors.py`. The router is thin by construction: it validates, calls the service, and renders. It re-decides nothing.

**Web** — a projects list with a create form, a project detail screen (lifecycle, details, assets, delete), loading skeletons and a route-scoped error boundary for both. `lib/api.ts` gained nine client functions, `lib/projects.ts` the vocabulary and labels, and `components/projects/` three components.

### Architecture decisions

**`legal_transitions` is a response field.** The single most consequential decision, and the one the step note demanded. Every project response carries exactly the states that project can move to, derived server-side. The frontend therefore holds *no* transition map — a Vitest case scans `lib/projects.ts`'s exports and fails if any of them maps a status to a collection of statuses, which is the shape a second state machine would take. A rules change now reaches every client with no frontend deploy.

**A transition is a `POST` to a sub-resource, not a `PATCH` of `status`.** A `PATCH` presents the status as a field a client may set. It is not: the server decides whether the move is coherent and refuses most of them. `POST /transitions` says that in the URL.

**404 for a project, 403 for a workspace.** Deliberately asymmetric, and both are "one answer per question, regardless of cause". A workspace id the caller supplied answers 403 either way, so it cannot be used to test which workspaces exist. A project id inside a workspace they do belong to answers 404, because invisible and absent are the same fact from their side. Recorded in [[API Conventions]] as a general rule rather than only here.

**Every live member writes.** No owner/admin asymmetry, unlike AI settings — projects are the workspace's shared work, and a member who cannot create one cannot use the product. **No project-specific permission was added**: that is a decision about the role model, and the first question it must answer ("may I delete someone else's project?") is one [[Projects]] does not.

**The state machine was not touched.** `ProjectService` was consumed exactly as [[STEP-20 Projects Schema and Lifecycle]] left it. The only change to the domain model was the asset-kind defect below, which was a schema error rather than a model change.

### Defects found and fixed

**`AssetKind` was free text, and the database refuses free text.** The API's `kind` was written as a bounded string on the reasoning that asset kinds were not settled. `ck_assets_kind_valid` permits exactly `document`, `image`, `video`, `audio`. So the API accepted `kind: "script"`, validation passed, and PostgreSQL raised `CheckViolation` — **a client's malformed request reported as a 500**, with a constraint name in the log instead of a usable message.

Fixed by typing `AssetKind` as a `StrEnum` mirroring the constraint, propagated to the frontend as a closed union, and surfaced in the UI as a `<select>` rather than a text input — an interface offering a value the database refuses teaches the user to guess. Three tests now guard it: one reads `pg_constraint` and compares in both directions, one posts an asset of every kind through the real route, and one asserts an invalid kind is 422 rather than 500.

**Only a live database could have found it.** The generalizable rule is recorded in [[Table - assets#`kind` is a closed vocabulary, and the API must mirror it exactly]]: *wherever the database constrains a value to a set, the outermost schema enumerates that same set.* A constraint the edge does not know about is a 500 waiting for its first user.

**Two smaller ones, both caught before commit.** A `surface-hover` Tailwind class that does not exist in the design tokens (the real token is `surface-raised`) — invented rather than checked, which is exactly what the Design Rules forbid. And an `isProjectStatus` guard first written inside the `"use server"` actions module, where only async functions may be exported; it moved to `lib/projects.ts` alongside the same constraint `lib/form-state.ts` already records.

### Validation

- **68/68 checks against the live development database**, driving the real routes in-process through `TestClient`. Every seeded row removed afterwards and verified to zero across all four tables.
- The four Validation items specifically: an illegal transition **is** 409 through HTTP and a legal one returns the updated project; another tenant's project **is** 404 and is indistinguishable from an invented id; `legal_transitions` **matches** `legal_transitions_from` in all nine states, walked through real transitions; **no route** returns another tenant's project, asserted across all six routes taking a project id, with the project confirmed untouched afterwards.
- API: ruff, ruff format, `mypy app` (60 files), 343 passed.
- Web: typecheck, lint, 113 tests, production build with both routes correctly dynamic.

**The 34 database-backed API tests skip locally** — the pytest harness still cannot reach a test database (STEP-19's unfixed pooler username mismatch, and no local PostgreSQL). The probe above exists precisely because CI would otherwise be the first place they ran, which is what made STEP-20 go red.

### Limitations, stated rather than discovered

- **No workspace switcher.** Inherited from STEP-19 and now more pressing: the constraint bounds a user's actual work, not only their settings. Disclosed on screen.
- **No asset upload.** `storage_path` is null on everything these routes create. Choosing a backend is an ADR, and the step that adds one owes it a deletion path ([[CLAUDE|CLAUDE.md]] §16).
- **No idempotency keys.** A retried creation makes a second project. Bounded — a duplicate a user can delete, not a duplicate charge — and it should be one decision taken once across the API.
- **`GET /projects` is unpaginated**, and is the first genuinely unbounded collection. [[API Endpoints]] now names it as where the pagination convention should be settled.

---

## Navigation

- **Previous:** [[STEP-20 Projects Schema and Lifecycle]]
- **Next:** [[STEP-22 Minimum Workflow Engine]]
- **Parent:** [[Build Plan]]
