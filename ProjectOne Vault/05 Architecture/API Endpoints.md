---
title: API Endpoints
category: Architecture
status: stable
version: "1.0"
last_updated: 2026-08-02
tags: [backend, api, standards, documentation]
aliases: ["Endpoint Reference", "API Reference"]
---

# API Endpoints

**Every endpoint ProjectOne serves**, as of [[STEP-13 Auth Users Workspaces Endpoints]]. This is the contract the frontend consumes from [[STEP-16 Sign Up and Sign In UI]] onward.

Each entry documents only what is **specific to that endpoint**, exactly as [[API Endpoint Template]] instructs. The shared contract — the `/api/v1` prefix, the `{"detail", "request_id"}` error envelope, the correlation id, the generic 401/403/422 behaviour — is [[API Conventions]] and is deliberately not restated fourteen times. A reader needing it goes there once.

> [!note] One note, not one note per endpoint
> The template's structure is applied per endpoint below rather than as fourteen near-identical files. Most of what a separate file would hold is the shared contract, and duplicating that is precisely the drift [[API Conventions]] exists to prevent. A single endpoint warrants its own note when it grows detail this table cannot carry — a request/response body worth a worked example, or a workflow spanning several calls.

## Conventions Applying to Everything Below

- **Base path:** `/api/v1`. `/health` is the one unversioned route ([[API Conventions#Versioning]]).
- **Authentication:** every endpoint below requires `Authorization: Bearer <token>` except where the table says otherwise.
- **Errors:** `401` unauthenticated, `403` refused, `422` malformed, `404` unmatched route, `429` rate limited — all in the standard envelope.
- **Identity is never accepted from a body.** No endpoint takes a `user_id` or `owner_id` naming *the caller*; that always comes from the verified token. Where a body does carry a user id (adding a member, transferring ownership) it names a **target**, and the caller's permission over that target is checked separately.

## Health

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /health` | — | Readiness, including database connectivity. **503** when a dependency is unreachable. Unversioned and never rate limited. |

## Authentication

Established by [[STEP-10 Authentication Backend]]; see [[Authentication Implementation]] for how a token becomes an identity.

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /api/v1/auth/sign-up` | — | **201.** Returns `email_confirmation_required` when the project issues no session. **400** on rejection, with a deliberately generic message — "User already registered" would make this an account-enumeration oracle. Rate limited **5/min**. |
| `POST /api/v1/auth/sign-in` | — | Returns access + refresh tokens. Rate limited **10/min**. |
| `POST /api/v1/auth/sign-out` | Bearer | Revokes the session **upstream** at Supabase, not client-side — a local discard leaves the token valid until it expires. |
| `POST /api/v1/auth/refresh` | — | Exchanges a refresh token. Rate limited **30/min**. |
| `GET /api/v1/auth/me` | Bearer | The caller's profile; provisions the `public.users` row on first use. |

**503, not 401, when Supabase is unreachable.** The caller's credentials were never judged, so reporting "invalid credentials" during an outage would both mislead the user and hide the outage.

## Workspaces

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces` | Bearer | — | Workspaces the caller belongs to. No `WHERE user_id` clause: the RLS policy does the filtering. |
| `POST /api/v1/workspaces` | Bearer | — | **201.** Creates the workspace and the caller's owner membership **in one transaction**, over the audited privileged path — the two-row bootstrap a client cannot perform ([[#Why creation needs a privileged path]]). No permission required: there is no existing workspace to hold one in. |
| `PATCH /api/v1/workspaces/{id}` | Bearer | `UPDATE_WORKSPACE` | Rename. **404** when the workspace was soft-deleted between the permission check and the write. |
| `GET /api/v1/workspaces/{id}/permissions` | Bearer | `VIEW_WORKSPACE` | The caller's own role and everything it permits. A convenience for rendering a UI that matches what the server will allow — **never the enforcement**. |
| `GET /api/v1/workspaces/{id}/export` | Bearer | `EXPORT_WORKSPACE_DATA` | Every record the workspace holds, across every registered store. Not held by `member`: a bulk copy of everyone's data is a different act from reading one's own screens. |
| `DELETE /api/v1/workspaces/{id}/data` | Bearer | `DELETE_WORKSPACE` | Soft-deletes every erasable record. Returns per-store counts. `audit_log` always reports **0** — see [[#Audit trail]]. |

### Why creation needs a privileged path

The `workspace_members` INSERT policy requires the caller to already belong to the workspace being written to, and a creator does not — the workspace did not exist a statement ago. Verified against a live database during STEP-13: the `workspaces` row inserts fine and the membership row is refused. That is deliberate ([[RLS Policy Pattern]]), and it forces creation through an audited service path instead of letting a client assemble a tenant boundary row by row. `test_a_client_cannot_bootstrap_a_workspace_by_direct_insert` asserts the refusal permanently.

## Membership

The rules are [[Authorization Model]]'s and are enforced in the database; these routes expose them.

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces/{id}/members` | Bearer | `VIEW_WORKSPACE` | Live members with their profiles. **Excludes removed members explicitly** — the SELECT policy no longer filters `deleted_at`, so the query must. |
| `POST /api/v1/workspaces/{id}/members` | Bearer | `MANAGE_MEMBERS` | **204.** Body: `{"user_id": uuid, "role": "member"\|"admin"\|"owner"}`, defaulting to `member`. Only an **owner** may grant `owner`. Runs over the ordinary tenant connection — this is *not* the bootstrap case. |
| `DELETE /api/v1/workspaces/{id}/members/{user_id}` | Bearer | `REMOVE_MEMBER` | **204.** Ranked: an owner removes admins and members, an admin removes members only. Self-removal is refused — that is `leave`. **409** if it would orphan the workspace. |
| `POST /api/v1/workspaces/{id}/leave` | Bearer | `LEAVE_WORKSPACE` | **204.** Every role holds this. **409** for the last owner, with a message naming ownership transfer as the remedy. |
| `POST /api/v1/workspaces/{id}/ownership` | Bearer | `TRANSFER_OWNERSHIP` | **204.** Body: `{"successor_id": uuid}`. Owner only. Promotes the successor and demotes the caller to `admin`, atomically. Transfer does **not** eject the outgoing owner — leaving is a separate act. |

### Adding members is by user id, not email

The project owner's decision on 2026-08-01. An email-keyed endpoint reveals whether an address has a ProjectOne account unless every response is identical either way, and a full invitation flow — pending state, tokens, delivery — is a larger scope than this step.

**Consequence, stated rather than discovered:** someone with no ProjectOne account cannot yet be added to a workspace. They must sign up first. A real invitation flow is unscheduled.

### 403 is deliberately indistinguishable

A caller whose role is too low and a caller who is not a member at all receive the **same status and the same body**. A difference would turn any workspace id into an existence oracle. Asserted by `test_an_outsider_adding_a_member_is_refused_identically_to_a_role_failure`.

## Audit trail

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces/{id}/audit` | Bearer | `VIEW_WORKSPACE` | Recent actions, newest first. `?limit=` 1–200, default 50. |

Readable by **every live member**, not admins only: a trail whose subjects cannot see it protects a workspace's administrators from its members rather than the reverse.

Recorded actions: `workspace.created`, `member.added`, `member.removed`, `member.left`, `ownership.transferred`. Each carries the actor's id and their email **as it was at the time** — a point-in-time snapshot, so the record survives the account changing or going away.

**The trail is append-only and cannot be tampered with.** No INSERT policy (writes come only from the privileged path, so a client cannot forge entries), no UPDATE or DELETE policy, and no UPDATE/DELETE/TRUNCATE grant — `TRUNCATE` matters most because it is not subject to RLS at all. Asserted directly against the database in `test_audit_log.py`.

**It is exportable but not erasable**, and that asymmetry is a documented legal exception ([[CLAUDE|CLAUDE.md]] §16): audit logs are retained on their own schedule because they exist precisely to survive the events they record. Otherwise anyone holding `DELETE_WORKSPACE` could destroy the evidence of what they did on the way out. A workspace erasure reports `"audit_log": 0`, which **discloses** the exception rather than hiding it.

## Not Built Yet

Recorded so the next reader does not assume otherwise:

- **User-facing endpoints beyond `/auth/me`.** There is no `PATCH /users/me` and no way to set a display name. Nothing needs it until there is a UI ([[STEP-16 Sign Up and Sign In UI]]).
- **Workspace deletion itself.** `DELETE /workspaces/{id}/data` erases contents; the workspace row remains. Deleting the workspace itself needs the last-owner and orphaning questions answered deliberately.
- **Invitation of non-users.** See above.
- **Idempotency keys.** `POST /workspaces` is the first endpoint creating a resource from a client-supplied request, so it is the first that could benefit. [[API Architecture]] calls for idempotency where appropriate; a retried creation currently makes a second workspace.
- **Pagination.** Every collection here is bounded by construction — a caller's workspaces, a workspace's members. The audit trail takes a bounded `limit` rather than a cursor. The first genuinely unbounded collection is where a pagination convention should be settled.

---

## Navigation

- **Previous:** [[API Conventions]]
- **Next:** [[Web Session Handling]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[API Conventions]] · [[API Endpoint Template]] · [[Authentication Implementation]] · [[Authorization Model]] · [[API Architecture]] · [[Table - audit_log]]
