---
title: API Endpoints
category: Architecture
status: stable
version: "1.4"
last_updated: 2026-08-16
tags: [backend, api, standards, documentation]
aliases: ["Endpoint Reference", "API Reference"]
---

# API Endpoints

**Every endpoint ProjectOne serves**, as of [[STEP-22 Minimum Workflow Engine]]. This is the contract the frontend consumes from [[STEP-16 Sign Up and Sign In UI]] onward.

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
| `PATCH /api/v1/auth/me` | Bearer | Changes the caller's `display_name` ([[STEP-19 Settings and BYOK UI]]). Carries **no id** — the row written is always the verified caller's, and `users_update_self` refuses any other. Runs over the *tenant* connection, never the privileged `UserRepository` path that provisioning uses. |

**`email` is deliberately not editable.** The address is authoritative in Supabase Auth and reconciled into `public.users` on every authenticated request, so a write here would be silently reverted on the user's next request. Changing an address needs a verification flow that does not exist yet.

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

## AI settings — providers, budgets and spend

Added by [[STEP-19 Settings and BYOK UI]]. **The first HTTP routes that reach the AI layer at all** — [[STEP-17 AI Router and Provider Abstraction]] built the router with no routes and [[STEP-18 AI Cost Governance Controls]] built the ceilings with none, so every route here is on the critical path for both tenant isolation and spend.

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces/{id}/ai/providers` | Bearer | `VIEW_WORKSPACE` | Provider name and `last_four` only. **Never key material.** |
| `PUT /api/v1/workspaces/{id}/ai/providers/{provider}` | Bearer | `UPDATE_WORKSPACE` | Stores or replaces a key. Idempotent on (workspace, provider). Audited. Rate limited **10/min**. **422** for an unknown provider or an implausibly short key. |
| `DELETE /api/v1/workspaces/{id}/ai/providers/{provider}` | Bearer | `UPDATE_WORKSPACE` | Soft-deletes the key. **204**, or **404** when none was stored — a false confirmation is worse than an error for a security action. Audited. |
| `GET /api/v1/workspaces/{id}/ai/budgets` | Bearer | `VIEW_WORKSPACE` | Ceilings, usage, period and breaker state. |
| `PUT /api/v1/workspaces/{id}/ai/budgets` | Bearer | `UPDATE_WORKSPACE` | Sets `limit_usd` and optionally `period_days`. Audited. Rate limited **10/min**. |
| `GET /api/v1/workspaces/{id}/ai/spend` | Bearer | `VIEW_WORKSPACE` | Spend ledger, newest first. `?limit=` 1–200, default 50. |

### No route can return a stored key

`ProviderCredentialService.key_for` is the only method in the codebase producing a plaintext provider key, and **no route calls it**. The response type carries `id`, `provider` and `last_four` and has no field capable of holding a key, so a future route returning it cannot leak one by accident.

Rotation is therefore **replace, never reveal** — a user who has lost their key stores a new one. Proven by grep against real response bodies rather than by reading the serializer, the [[STEP-16a Developer Session Inspector]] standard.

### Members read, owners and admins write

Deliberate asymmetry, and both halves matter. A tripped ceiling must be explainable to the person whose request it refused, so every live member can read budgets, spend and which providers are configured. Changing a key or a ceiling is billing-adjacent and belongs to the roles that already control such settings.

Enforced in **both layers**: a `requires(...)` dependency on the route *and* an RLS policy scoped to `owner`/`admin`. The policy makes the write impossible; the dependency makes the answer honest — without it a member would receive a 500 or an unaffected row where a 403 is the truth.

### `spent_usd` is unwritable by three independent mechanisms

The running total every ceiling is enforced against is not a client-writable value:

1. **`BudgetUpdateRequest` forbids extra fields**, so sending it is a **422** rather than a silent discard.
2. **The handler never passes it on.**
3. **A column-level grant** (migration `c9d3b71e08af`) replaced the table-wide `UPDATE` with one on `limit_usd` and `period_interval` only, so the request connection cannot write it even if the two layers above were bypassed.

The third exists because it is the one that holds when a future route forgets. This closes the exposure [[STEP-18 AI Cost Governance Controls]] recorded — see [[Table - ai_budgets]].

### Governance refusals

Routes raise; they do not map. A ceiling or execution limit reaches the client as **402**, a shutdown or tripped breaker as **503** with `Retry-After`, through the handler table in `app/core/errors.py`.

## Projects and assets

Added by [[STEP-21 Projects UI]], over the schema and lifecycle [[STEP-20 Projects Schema and Lifecycle]] built. **The first routes reaching a workspace's actual work** rather than its configuration, and the first where every live member writes. [[STEP-28 Asset Upload and Download]] added the two routes that move bytes.

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces/{id}/projects` | Bearer | `VIEW_WORKSPACE` | Live projects, newest first. **Archived projects are included** — archive is a lifecycle state, not a deletion. Unpaginated (see [[#Not Built Yet]]). |
| `POST /api/v1/workspaces/{id}/projects` | Bearer | `VIEW_WORKSPACE` | **201.** Body: `{"name", "description"?}`. Always created in `idea` — **`status` is not accepted** and sending it is a 422. Rate limited **30/min** per user. |
| `GET /api/v1/workspaces/{id}/projects/{project_id}` | Bearer | `VIEW_WORKSPACE` | One project, with its `legal_transitions`. **404** when absent *or* hidden by RLS — deliberately one answer ([[#Why a project is 404 where a workspace is 403]]). |
| `PATCH /api/v1/workspaces/{id}/projects/{project_id}` | Bearer | `VIEW_WORKSPACE` | Name and description. **Cannot change status** — no such field, and sending one is a 422. An explicit `null` description clears it. |
| `POST /api/v1/workspaces/{id}/projects/{project_id}/transitions` | Bearer | `VIEW_WORKSPACE` | Body: `{"status"}`. **409** when the lifecycle refuses the move, **422** when the value is not a state at all. Returns the updated project, whose `legal_transitions` now describe the new state. |
| `DELETE /api/v1/workspaces/{id}/projects/{project_id}` | Bearer | `VIEW_WORKSPACE` | **204.** Soft-deletes. **Not the same as archiving.** **404** on a second call — a false confirmation would claim something happened that did not. |
| `GET /api/v1/workspaces/{id}/projects/{project_id}/assets` | Bearer | `VIEW_WORKSPACE` | Live assets, **oldest first** — creation order is the order the work happened in. |
| `POST /api/v1/workspaces/{id}/projects/{project_id}/assets` | Bearer | `VIEW_WORKSPACE` | **201.** Body: `{"name", "kind"}`. `kind` is a closed vocabulary: `document`, `image`, `video`, `audio`. **Records an asset; uploads nothing** — `storage_path` stays null. Rate limited **60/min** per user. |
| `POST /api/v1/workspaces/{id}/projects/{project_id}/assets/upload` | Bearer | `VIEW_WORKSPACE` | **201.** `multipart/form-data`: `file`, `name`, `kind`. **The only route that stores bytes.** Returns the asset with `storage_path` populated. Rate limited **60/min** per user. See [[#Uploads are validated four ways]]. |
| `GET /api/v1/workspaces/{id}/projects/{project_id}/assets/{asset_id}/download` | Bearer | `VIEW_WORKSPACE` | Returns `{"url", "expires_in_seconds"}` — a **signed URL valid 15 minutes**, never the bytes and never a bucket path. **404** when the asset holds no file. |
| `DELETE /api/v1/workspaces/{id}/projects/{project_id}/assets/{asset_id}` | Bearer | `VIEW_WORKSPACE` | **204.** **404** when the asset is not attached to *that* project — every path segment is enforced, not just the ones the query uses. |

### Uploads are validated four ways

Added by [[STEP-28 Asset Upload and Download]]. An upload endpoint is a classic injection surface, so validation is the feature rather than a detail of it. Four **independent** checks, cheapest first — none is load-bearing alone:

1. **Size**, against a **100 MB per-asset ceiling**, enforced while the body streams rather than after it lands. **413** when exceeded.
2. **Declared MIME type**, against an allowlist derived from `kind`. A type valid for another kind is refused, so an `image` row cannot hold a PDF. **415**.
3. **Extension**, against the same allowlist entry. Absent is permitted; wrong is **415**.
4. **Content sniffing** — the file's leading bytes must agree with what was declared. **A `.png` whose content is a Windows executable is refused**, and this is the check that gives the other three meaning: a type and an extension are strings the client chose.

An empty upload is **400**. No refusal message ever echoes the filename back — a caller-controlled string reflected into a response is how one injection becomes two.

**The size ceiling and the absence of resumable upload are one decision.** `StorageProvider.put` takes bytes, so an accepted upload is held in memory in full; raising the ceiling without changing the transport raises what a single request can consume. Larger media is a reason to revisit the transport, not the number.

### A download is a capability, not a location

The download route returns a **signed URL**, never proxied bytes and never a public path. Proxying would put every megabyte through an API worker; a durable path would be a permanent grant issued for a momentary need.

**15 minutes**, chosen at the call site rather than defaulted in the backend — `signed_url` deliberately has no default, because the right lifetime depends on what is being handed out. A signed URL is a **bearer capability**: anyone holding the string can read the object with no further authentication, so the window is long enough for a browser to fetch an asset it is about to display and short enough that a URL leaked through a referrer header or a screenshot stops working before it is useful.

**Cross-tenant access fails at the route, before anything is signed.** The membership gate refuses a non-member, and the asset row is then resolved through the tenant connection where RLS refuses another workspace's row — so no URL is generated for a caller who should not have one. A route that signed first and checked afterwards would already have produced the capability it was about to refuse.

`storage_path` is **opaque to clients**: a logical name, not a URL and not a path. Bytes are reached only by exchanging it here — see [[Table - assets#`storage_path` holds a logical name, not a path]].

### Every live member writes here

Unlike AI settings, there is **no owner/admin asymmetry**. Projects are the workspace's shared work: a member who cannot create or advance one cannot use the product. `requires(VIEW_WORKSPACE)` therefore gates every route, and its job is the *tenant* boundary rather than a role distinction.

**There is no project-specific permission**, deliberately. Adding one to [[Authorization Model]] is a decision about the role model rather than a detail of a UI step, and the permission that would be needed first — "may delete someone else's project" — is a question [[Projects]] does not answer yet.

### The API owns the lifecycle rules; clients never copy them

Every project response carries **`legal_transitions`**: exactly the states that project can move to next, derived server-side from `legal_transitions_from` ([[Project Lifecycle]]).

This field exists so a UI never needs its own state machine. Two copies of a state machine diverge the first time the rules change, and the divergence shows up as a button producing a 409 — or worse, a legal move no screen offers. Because the list is per project and per state, a rules change reaches every client with no frontend deploy.

`test_legal_transitions_match_the_service_in_every_state` walks a project through all nine states and compares the field against the service at each one; `test_offering_only_legal_transitions_would_never_produce_a_409` submits every advertised move and asserts each succeeds.

### 409 and 422 are different refusals

- **422** — the value is not a lifecycle state. `ProjectTransitionRequest` types it as an enum, so this is refused before any service code runs.
- **409** — the value *is* a state, but not reachable from the current one. The message names both states, which is safe (the caller already knows the current status) and is the difference between an actionable error and a mystery.

Collapsing them would send a client debugging a typo through a lifecycle diagram.

### Why a project is 404 where a workspace is 403

The two look inconsistent and are not:

- A **workspace** id answers **403** whether the caller is a non-member or under-privileged. The caller supplied that id as the thing they claim access to, so a 404 would confirm which workspace ids exist.
- A **project** id inside a workspace they *do* belong to answers **404**, because an invisible project and an absent one are the same fact from their side — and the workspace gate has already refused anyone who does not belong.

The rule underneath both: **one answer per question, regardless of cause.** `test_a_project_id_is_not_an_existence_oracle` asserts a hidden project and an invented id are indistinguishable in both status and body.

### Archive is a state; delete removes

They are separate operations with separate routes, and the API keeps them separate because presenting one as the other would misrepresent what a user just did:

- **Archive** (`POST /transitions` with `archive`) is terminal but keeps the project in the workspace, in the listing, with its assets, as a record of finished or abandoned work.
- **Delete** removes it from the listing. Soft, so the row survives with `deleted_at` set.

Deletion is permitted from any state, archived included — requiring archive first would be ceremony, not a safeguard, since the deletion is soft either way. See [[Project Lifecycle#Archive Is Not Deletion]].

### Assets are recorded, not uploaded

`storage_path` is null on everything these routes create and **no bytes cross the API**. No storage backend is chosen, and choosing one is an ADR ([[CLAUDE|CLAUDE.md]] §10/§28) — the step that adds it also owes it a deletion path (§16). The field is present rather than hidden so a client can render "no file attached" honestly rather than being unable to tell an unbuilt feature from an empty one.

`kind` is a **closed vocabulary** enforced by `ck_assets_kind_valid`. It was first written as free text, and driving the routes against a real database found the consequence immediately: the API accepted `kind: "script"` and PostgreSQL refused it, turning a client error into a 500. Typing it makes the same request a 422 naming the four valid values.

## Workflow runs

Added by [[STEP-22 Minimum Workflow Engine]]. **The first routes that cause AI spend without a human watching each call**, which is why the approval gate below is the centre of this surface rather than a detail of it.

| Endpoint | Auth | Permission | Notes |
|---|---|---|---|
| `GET /api/v1/workspaces/{id}/workflows/catalog` | Bearer | `VIEW_WORKSPACE` | Workflow names this deployment can run. Served from the registry so a client picker cannot offer one the server lacks. |
| `GET /api/v1/workspaces/{id}/workflows/runs` | Bearer | `VIEW_WORKSPACE` | Recent runs, newest first, each with its steps. Bounded by a repository limit — run count grows with automation, not human effort. |
| `POST /api/v1/workspaces/{id}/workflows/runs` | Bearer | `VIEW_WORKSPACE` | **201.** Body: `{"workflow_type", "project_id"?}`. Executes until the run finishes, pauses or fails. **422** for an unknown workflow, **404** for another tenant's project. Rate limited **20/min** per user. |
| `GET /api/v1/workspaces/{id}/workflows/runs/{run_id}` | Bearer | `VIEW_WORKSPACE` | One run with its full step history. **404** when absent *or* hidden by RLS. |
| `POST /api/v1/workspaces/{id}/workflows/runs/{run_id}/approval` | Bearer | **`UPDATE_WORKSPACE`** | Approves the step the run is waiting on and continues. **409** when the run is not awaiting approval. |
| `POST /api/v1/workspaces/{id}/workflows/runs/{run_id}/resume` | Bearer | `VIEW_WORKSPACE` | Continues an interrupted or failed run. **409** for a completed run, and **409** for one awaiting approval — resuming is not approving. |

### A failed run is a 201, not a 500

The least obvious rule on this surface and the most important. A run whose step fails returns **201 with the run in `failed`**, because the request succeeded: the run was created, executed, and recorded its outcome. Reporting it as a server error would tell the client its call did not happen when it did, and would lose the run id they need to investigate.

What *is* an error status is a request that could never have produced a run — an unknown workflow (422), a run that cannot be seen (404), a run whose state refuses the action (409).

### Approval is owner/admin; everything else is any live member

The project owner's decision on 2026-08-08. A gated step is by definition one that spends money, publishes, or acts externally — the same class of consequence already guarding AI keys and spend ceilings, so it reuses `UPDATE_WORKSPACE`.

Starting, reading and resuming are `VIEW_WORKSPACE`, matching projects: a member who cannot run a workflow on their own project cannot use the product. **No new permission was added** — `workflow:approve` would change the role model, which is an authorization decision rather than a detail of this step.

### Resuming is not approving

`POST /resume` answers **409** for a run in `awaiting_approval`, and it must: resuming carries only `VIEW_WORKSPACE`, so letting it clear a gate would let anyone able to restart a run — including an automated retry — bypass the human [[CLAUDE|CLAUDE.md]] §15 puts behind it.

### One approval covers one step

Approving continues the run until it finishes or reaches the **next** gated step, where it stops again. There is no "approve everything from here": that is autonomous execution, which §15 requires to be a documented, configured opt-in rather than a side effect of clicking approve.

See [[Workflow Execution]] for the full model.

## Not Built Yet

Recorded so the next reader does not assume otherwise:

- **User-facing endpoints beyond `/auth/me`.** `PATCH /api/v1/auth/me` now sets a display name ([[STEP-19 Settings and BYOK UI]]); nothing else about a user is editable, and changing an email address remains unbuilt.
- **Workspace switching.** A user belonging to several workspaces can currently only configure the first — the web application resolves one server-side and discloses the limitation on screen. **[[STEP-21 Projects UI]] inherits this rather than resolving it**: a projects list is workspace-scoped, so the constraint now bounds a user's actual work and not only their settings. That makes it more pressing than it was, and it remains unscheduled.
- **Asset upload.** `POST /projects/{id}/assets` records that an asset exists; no storage backend is chosen and no route serves bytes. Needs an ADR, and the step that adds it owes it a deletion path ([[CLAUDE|CLAUDE.md]] §16).
- **Project-level permissions.** Every live member may create, edit, transition and delete any project in their workspace. "May delete someone else's project" is the first question a finer model would have to answer, and [[Projects]] does not answer it.
- **Workspace deletion itself.** `DELETE /workspaces/{id}/data` erases contents; the workspace row remains. Deleting the workspace itself needs the last-owner and orphaning questions answered deliberately.
- **Invitation of non-users.** See above.
- **Idempotency keys.** `POST /workspaces` was the first endpoint creating a resource from a client-supplied request; `POST /projects` and `POST /assets` are now the second and third. [[API Architecture]] calls for idempotency where appropriate; a retried creation currently makes a second project. The consequence is bounded — a duplicate a user can delete, not a duplicate charge — but it should be **one decision taken once** across the API rather than invented per route.

  **[[STEP-23 AI Chat End to End]] settled it for one route, because there the consequence is not bounded.** A retried chat completion would be a duplicate *charge*, so `POST /chat/conversations/{id}/completion` is idempotent per turn: the client names the `user_message_id` it is answering, and the server claims that turn with a conditional `UPDATE ... WHERE turn_status = 'pending'` before contacting a provider. Concurrent callers observe the claim and are refused with 409.

  Two properties of that design generalise, and the pending API-wide decision should account for them:

  1. **The key is the resource being acted on, not a client-generated nonce.** The user message already exists and already has an id, so no extra header or token was needed.
  2. **A unique constraint is not an idempotency mechanism when the side effect is external.** It was tried first and rejected: a unique index on the reply refuses the duplicate *row* only after both callers have already invoked and been billed by the provider.
  3. **An idempotency key the client cannot see is not usable.** `turn_status` is carried on every `MessageResponse` for exactly this reason. It existed in the database from the first migration but was not exposed, so a client had no way to tell an answered question from one whose provider call had failed — and therefore no way to name a turn worth retrying. Manual testing found three unanswered questions accumulated in a single conversation, each retryable by contract and unreachable in practice. **A retryable operation must expose both its state and its key**, or the only reachable action is to start a new one.

  What remains genuinely open is the crash window — a process dying after a provider accepted a request cannot be made exactly-once without provider-side idempotency keys. STEP-23 leaves such a turn visibly stuck rather than retrying it; closing it properly is a dedicated ADR-backed step covering every AI feature.
- **Pagination.** `GET /projects` is the first genuinely unbounded collection: a workspace's project count is bounded only by human effort today, but [[Workflow Engine]] will let a workspace create projects programmatically. The repository's stable `created_at DESC, id DESC` ordering is what makes adding keyset pagination later a change to one query rather than a redesign. **This is where the pagination convention should now be settled.**

---

## Navigation

- **Previous:** [[API Conventions]]
- **Next:** [[Web Session Handling]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[API Conventions]] · [[API Endpoint Template]] · [[Authentication Implementation]] · [[Authorization Model]] · [[API Architecture]] · [[Table - audit_log]]
