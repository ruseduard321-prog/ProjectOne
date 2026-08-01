---
title: Authorization Model
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [security, authorization, rbac, multi-tenancy, standards]
aliases: ["RBAC", "Role Model", "Permission Model"]
---

# Authorization Model

What `owner`, `admin` and `member` actually mean, where the rules are enforced, and which layer wins when they disagree. Established by [[STEP-11 Authorization and RBAC]] and binding from that point on.

`workspace_members.role` has existed since [[STEP-08 Users and Workspaces Schema]], constrained to three values, and until STEP-11 **no policy and no code read it**. Three names with no semantics are not an authorization model — they are a vocabulary that drifts, with each endpoint inventing its own idea of what "admin" means. This note is the single definition.

## Where Roles Are Enforced

**Both layers, and the database is authoritative.** This was the load-bearing decision of STEP-11, and both halves are deliberate:

| Layer | Answers | Failure mode |
|---|---|---|
| RLS policy ([[RLS Policy Pattern]]) | Which rows the command may touch | Silently affects zero rows |
| `AuthorizationService` | Whether the caller may attempt it at all | Raises, becomes a **403** |

Neither alone is sufficient:

- **Policies alone** are safe and behave badly. A member updating a workspace they may not update matches no row, so the statement reports `UPDATE 0` and the caller receives a cheerful 200 describing a change that never happened. A policy cannot return 403 — it has no idea an HTTP request exists.
- **The service layer alone** behaves well and is unsafe. One future endpoint that forgets the dependency is an unguarded write path, and nothing about the query will look wrong ([[CLAUDE|CLAUDE.md]] §16).

The duplication is the point ([[CLAUDE|CLAUDE.md]] §16 — defence in depth). The risk it carries is two copies of a rule drifting apart, and that is answered by naming which copy wins:

> **If the RLS policies and the Python matrix disagree, the policies are correct and the matrix is a bug.**

`apps/api/app/core/permissions.py` holds the single statement of the model that both are written from. `test_write_roles_are_exactly_those_holding_update` fails when the two stop agreeing.

## How a Request's Role Is Resolved

**Per request, from `workspace_members` — never from a token claim.**

A role carried as a Supabase custom claim would be free to read and is the wrong trade. An access token lives about an hour, so demoting an admin would leave them fully privileged until their token expired — the invalidation window would be "up to one token lifetime", discovered rather than stated.

The lookup costs one indexed query against a table the RLS policies must consult anyway.

> **The invalidation window is one request.** A role changed in the database takes effect on the caller's very next request. Pinned by `test_a_role_change_takes_effect_on_the_next_request`.

The lookup itself runs over the **tenant connection**, subject to the same policies as everything else. Reading roles over the privileged connection would work and would make the authorization layer the one component in the system not subject to the isolation it enforces.

## The Role Matrix

| Permission | `owner` | `admin` | `member` |
|---|:---:|:---:|:---:|
| `workspace:view` — read the workspace and its members | ✅ | ✅ | ✅ |
| `workspace:update` — rename, change settings | ✅ | ✅ | — |
| `workspace:manage_members` — add, remove, change roles | ✅ | ✅ | — |
| `workspace:export` — export every record the workspace holds | ✅ | ✅ | — |
| `workspace:delete` — soft-delete the workspace itself | ✅ | — | — |

Read as: an owner may do anything; an admin runs the workspace day to day but cannot destroy it or take it over; a member participates and reads.

Two rows carry the most weight:

- **`admin` does not hold `workspace:delete`.** Deleting a workspace destroys every member's work, not only the actor's. Concentrating that in the single role that is also the `workspaces.owner_id` foreign key keeps "who can destroy this" answerable by looking at one column.
- **`admin` holds `workspace:export` but `member` does not.** An export is a bulk copy of everyone's data in the workspace, a materially different act from reading the screens one has access to. Treating it as ordinary read access is how a data-exfiltration path gets built by accident.

Permissions are named after **actions, not endpoints**. A permission named `can_call_patch_workspace` has to be reinvented the moment a second route performs the same action, and the two copies then drift.

## Requiring a Permission

Declarative at the route, never an `if` inside a handler ([[CLAUDE|CLAUDE.md]] §12):

```python
@router.patch("/{workspace_id}")
def rename_workspace(
    workspace_id: uuid.UUID,
    _role: Annotated[WorkspaceRole, Depends(requires(WorkspacePermission.UPDATE_WORKSPACE))],
) -> WorkspaceResponse: ...
```

`requires(...)` is a factory because a FastAPI dependency cannot take arguments of its own. The permission is captured in the route declaration, which is where it belongs and where a reviewer sees it.

The `workspace_id` path parameter is read from the URL **by name**, so every route using this must declare it — FastAPI raises at startup if it does not, making a mismatch a boot failure rather than a route silently authorizing against nothing. It is never taken from a request body: a body-supplied id is the caller choosing which workspace to authorize against, which is the caller choosing their own permission check.

**Services enforce their own permissions too**, where the operation must never run unauthorized regardless of caller. `DataOwnershipService` checks inside the service rather than at the route, because a future scheduled job or admin path has no HTTP route and would silently skip a route-level check.

## 401 Versus 403

`AuthorizationError` is deliberately **not** an `AuthError` subclass. Every `AuthError` maps to 401, and folding authorization into that hierarchy would make a permission failure indistinguishable from a credential failure.

| Code | Meaning |
|---|---|
| **401** | "I do not know who you are." No token, expired, bad signature, wrong issuer. |
| **403** | "I know exactly who you are, and the answer is still no." |

Conflating them is a correctness bug before it is a security one: a 401 tells a correct client its session is broken and sends it into a refresh loop over what is a settled refusal.

The mapping is registered **once**, as an exception handler in `app/main.py`, rather than repeated as a `try/except` in every router — a check whose HTTP mapping depends on each router remembering to catch it eventually surfaces as a 500.

> [!important] A non-member and an insufficient role return the same response
> `WorkspaceAccessError` (no live membership) and `AuthorizationError` (role too low) surface **identically** — same status, same body. A 404-versus-403 difference would reveal whether a workspace id exists at all, turning every endpoint taking one into an existence oracle. Only the log knows which happened.
>
> The body names neither the caller's role nor the required permission. That detail is a map of the permission model, and belongs in the log ([[CLAUDE|CLAUDE.md]] §24).

## Data Ownership: Export and Erasure

Structural only at this stage — the UI is a later step. It exists now because retrofitting deletion is expensive ([[CLAUDE|CLAUDE.md]] §16): the shape a feature stores data in decides whether it can be exported and erased at all.

**A registry, not a hardcoded query.** Deletion must be end-to-end — primary database, [[Memory System]], analytics event logs, search/cache layers. None of the latter three exist yet, and a service hardcoding today's tables would silently keep succeeding while missing them, reporting a completed erasure that erased a fraction of the data.

`ExportableStore` is the contract a store registers under, and `REGISTERED_STORES` is the checklist. **A feature that persists workspace data registers its store there, as part of its Definition of Done** ([[CLAUDE|CLAUDE.md]] §16 and §22). A store absent from the tuple is absent from every export and every erasure — visibly, at the wiring layer, rather than invisibly inside a query.

`ErasureResult` reports **per-store counts** rather than a success flag, because "deletion succeeded" is not a useful claim about a multi-store erasure.

> [!warning] Erasure of `workspace_members` does not work yet
> Not an authorization limit — a policy one. Soft-deleting any `workspace_members` row is rejected for every role, because STEP-09's SELECT policy filters `deleted_at IS NULL`. See [[RLS Policy Pattern]] for the reproduction. The store reports `0` rather than raising or bypassing RLS, so a caller sees that nothing was erased instead of a success message over data that is still there.

## What This Does Not Cover

- **Cross-workspace and platform-level roles.** There is no "platform admin" and no role that spans workspaces. Cross-tenant access remains default-forbidden and requires an ADR ([[CLAUDE|CLAUDE.md]] §16).
- **Per-resource permissions.** Roles are scoped to a workspace, not to individual projects or documents. Finer granularity is a change to this model, not an extension of it.
- **Membership management endpoints.** Adding and removing members belongs to [[STEP-13 Auth Users Workspaces Endpoints]], which owns the audited service path the INSERT policies require — and which will have to resolve the erasure limitation above.

---

## Navigation

- **Previous:** [[Authentication Implementation]]
- **Next:** [[Schema Overview]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[RLS Policy Pattern]] · [[Authentication Implementation]] · [[Authentication and Authorization]] · [[Privacy and Data Protection]] · [[Security Architecture]] · [[Table - workspace_members]]
