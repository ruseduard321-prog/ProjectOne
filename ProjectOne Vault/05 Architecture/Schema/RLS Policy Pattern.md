---
title: RLS Policy Pattern
category: Architecture/Schema
status: stable
version: "1.1"
last_updated: 2026-08-04
tags: [database, security, multi-tenancy, standards]
aliases: ["Row Level Security Pattern", "Tenant Isolation Pattern"]
---

# RLS Policy Pattern

The reviewed pattern **every tenant-scoped ProjectOne table copies**. Established by [[STEP-09 Row Level Security Policies]] and binding from that point on.

This exists so a new tenant table gets isolation by following a pattern that has been tested, rather than by improvising policies per table. RLS is the control standing between one customer's data and another's — an improvised version of it is a cross-tenant data breach waiting for its first bug ([[CLAUDE|CLAUDE.md]] §16).

> [!important] The standing rule
> **Every tenant-scoped table ships its RLS policy in the same migration that creates it.** A table without RLS is an incomplete migration, not a follow-up task. [[STEP-08 Users and Workspaces Schema]] is the single deliberate exception in this project's history and does not generalize — see [[Table Conventions#Row Level Security]].

## How Identity Reaches a Policy

`auth.uid()` — Supabase's `STABLE` function reading the `request.jwt.claim.sub` session setting:

```sql
SELECT coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
)::uuid
```

It returns **NULL when no JWT claim is set**, which is the property every policy below depends on: an unauthenticated session matches nothing and therefore sees nothing. Denial is the default, not a case someone has to remember to write.

[[STEP-10 Authentication Backend]] owns *setting* that claim on a request. Policies only consume it.

## The Membership Function

```sql
CREATE OR REPLACE FUNCTION public.app_current_user_workspaces()
RETURNS setof uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT wm.workspace_id
    FROM public.workspace_members wm
    WHERE wm.user_id = auth.uid()
      AND wm.deleted_at IS NULL
$$;
```

**Every tenant policy routes through this function.** A new tenant-scoped table's policy is, in the normal case, exactly one line:

```sql
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
```

Note what is **not** there: `deleted_at IS NULL`. Liveness belongs in the query, and putting it in a SELECT policy makes soft-deleting the table impossible — see [[#A SELECT policy that filters deleted at makes soft deletion impossible]].

### Why a function at all

A policy on `workspace_members` that subqueries `workspace_members` **recurses**. PostgreSQL raises:

```
infinite recursion detected in policy for relation "workspace_members"
```

This was verified against a live database before the migration was written, not assumed. A `SECURITY DEFINER` function reads memberships *outside* RLS, which breaks the cycle.

### Why it is safe

A `SECURITY DEFINER` function is itself a bypass vector — precisely the thing RLS exists to prevent — so each of these is a containment measure, not decoration:

| Measure | What it prevents |
|---|---|
| **No parameters** | A `workspaces_for(uuid)` signature would let any caller ask what *another* user can see. Reading identity from `auth.uid()` internally means a caller can only ask about themselves. |
| **`SET search_path = ''`** + schema-qualified names | A caller able to create objects could otherwise shadow `workspace_members` with their own table and have the function read it with the owner's rights. This is the classic definer privilege-escalation path. |
| **`STABLE`** | Read-only, and the planner may cache the result within a statement instead of re-running it per row. |
| **`EXECUTE` revoked from `PUBLIC`, `anon` and `service_role`** | See the warning below — revoking from `PUBLIC` alone is not enough. |
| **Returns only workspace ids the caller belongs to** | Never rows, never another user's data. The blast radius of the definer's rights is one column of ids the caller is entitled to by definition. |

> [!warning] Revoking from `PUBLIC` does not revoke from `anon`
> Supabase ships an `ALTER DEFAULT PRIVILEGES ... GRANT EXECUTE ON FUNCTIONS TO anon, authenticated, service_role` on the `public` schema. A newly created function is therefore granted to those roles **by name**, and `REVOKE ... FROM PUBLIC` does not remove a grant held explicitly by a named role.
>
> Observed during STEP-09 validation: after the `PUBLIC` revoke, `anon` still held `EXECUTE`. Any new `SECURITY DEFINER` function must revoke from the named roles explicitly. `test_definer_function_is_not_executable_by_anon` guards this.

## The Policies

Written **per command**, never as one `FOR ALL` policy. `FOR ALL` applies a single `USING` expression to SELECT, UPDATE and DELETE and reuses it as `WITH CHECK` for writes. That reads as economical and behaves subtly wrong: the condition under which a row may be *read* is not always the condition under which it may be *created*. Separating them means each grant is reviewable on its own, and INSERT — which has no `USING` clause at all — cannot be overlooked.

| Table | Command | Rule |
|---|---|---|
| `users` | SELECT | Self, or anyone sharing a live workspace |
| `users` | UPDATE | Self only, and cannot be reassigned to another identity |
| `workspaces` | SELECT | Live membership required |
| `workspaces` | UPDATE | **`owner` or `admin` only** ([[STEP-11 Authorization and RBAC]]) |
| `workspaces` | INSERT | The row must name the creator as `owner_id` |
| `workspace_members` | SELECT | Same workspace — **including soft-deleted rows** ([[STEP-11a Membership Removal Policy]]) |
| `workspace_members` | UPDATE | **Ranked removal: owner > admin > member; anyone may edit their own row, never their own `role`** |
| `workspace_members` | INSERT | Same workspace |

### The role predicate

[[STEP-11 Authorization and RBAC]] made the two UPDATE policies role-aware. Membership alone was never a sufficient test for a write: until then an ordinary `member` could rename the workspace and rewrite anyone's role row exactly like its owner.

Roles are tested through `app_current_user_workspaces_as(text[])`, the role-filtered sibling of the helper above, with the same containment measures for the same reasons:

```sql
USING (
    deleted_at IS NULL
    AND id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
)
```

**Its parameter is safe and STEP-09's parameterless design still holds.** The banned shape is a parameter naming *whose* access to inspect (`workspaces_for(user_id)`), which would let any caller ask what another user can see. This parameter names which *roles* to filter the caller's own memberships by; identity still comes from `auth.uid()` internally. Guarded by `test_role_function_only_ever_answers_about_the_caller`.

The role vocabulary and what each role permits are defined once, in `apps/api/app/core/permissions.py`. **If that matrix and these policies disagree, the policies are correct and the matrix is a bug** — see [[Authorization Model]].

### A SELECT policy that filters `deleted_at` makes soft deletion impossible

**This is the rule, not an exception — and calling it an exception is what made it cost two steps.**

`workspace_members` was the first table to hit it (STEP-11a) and `provider_credentials` the second ([[STEP-19 Settings and BYOK UI]]), because this note previously recorded the fix as a one-off and told every new table to filter `deleted_at` in each `USING` clause. Tables written after the fix copied the broken shape from the instruction rather than from the correction.

**The mechanism.** Revocation is an `UPDATE` that *sets* `deleted_at`, so the row it produces no longer satisfies a SELECT policy filtering `deleted_at IS NULL` — and PostgreSQL applies that policy to the resulting row when the statement's `WHERE` clause requires the row to be visible. The write is refused by the policy governing **reading**, with a message naming row-level security, which sends the reader to the UPDATE policy where nothing is wrong.

Established by narrowing rather than inference, against a live database during STEP-19:

| Statement | Result |
|---|---|
| `UPDATE ... SET last_four = '9999'` | **1 row** — the UPDATE policy passes |
| `UPDATE ... SET deleted_at = now()` | **refused** |
| the same, with `deleted_at` dropped from the SELECT policy | **1 row** |

> [!warning] The same latent defect remains on four tables
> `ai_budgets`, `ai_shutdown_switches`, `users` and `workspaces` all have a SELECT policy filtering `deleted_at IS NULL` **and** an UPDATE policy. Each becomes a live defect the moment a route soft-deletes that table over the request connection. None does today, which is why STEP-19 fixed only `provider_credentials` rather than widening its migration to tables it does not touch ([[CLAUDE|CLAUDE.md]] §29/§35) — but this is a known trap, not an unknown one, and the step that first soft-deletes any of them must fix its policy in the same change.
>
> Worth noting how invisible it is: `ProviderCredentialStore.erase` had been soft-deleting `provider_credentials` since STEP-17 as part of **workspace data erasure**, and was silently failing — a [[CLAUDE|CLAUDE.md]] §16 obligation broken with no test covering it, because nothing had ever revoked a key.

The fix, in both cases, is the same: the filter **moves out of the policy and into the queries**.

- **A policy answers "whose rows may this caller touch"** — a tenant question, which `deleted_at` has nothing to do with.
- **A query answers "which of those rows do I want"** — excluding removed members from a listing, which always was a query concern.

**What this does not weaken.** `app_current_user_workspaces()` still filters `deleted_at IS NULL` on the caller's *own* membership, so a removed member still loses access to everything immediately. That is the property STEP-09's isolation tests assert, and it is untouched. The tenant predicate is untouched too.

> [!warning] Every query on `workspace_members` must now say `deleted_at IS NULL` itself
> A listing that inherited the filter from the policy and never said so will now show removed members. `test_removed_members_are_excluded_from_listings` guards the shape; `test_the_select_policy_still_blocks_the_other_tenant` guards that the widening stopped at the workspace boundary.

**What genuinely widened:** a live member can read the soft-deleted membership rows of their own workspace — who used to be in a workspace you are in. Never another tenant's data, and information any member list showing "removed" states needs anyway.

### The last-owner rule is a trigger, not a policy

`trg_workspace_members_protect_last_owner` ([[STEP-11a Membership Removal Policy]]) refuses to leave a workspace ownerless. **It cannot be an RLS predicate**: it depends on how many owners remain *after* the statement, which means counting `workspace_members` from inside a policy on `workspace_members` — the recursion the helper function exists to break.

It closes **both** routes to an ownerless workspace, which is the part that is easy to get half-right:

- Soft-deleting the last owner (leaving, or being removed).
- **Demoting** the last owner — the same hole through a different statement.

`DEFERRABLE INITIALLY IMMEDIATE`, so ownership transfer can promote and demote in either order within one transaction. Without deferrability the rule would silently depend on statement ordering.

### `USING` versus `WITH CHECK`

`USING` decides which existing rows the command can *see*. `WITH CHECK` decides what a row is allowed to *become*. Both are required on UPDATE:

```sql
USING (id = auth.uid() AND deleted_at IS NULL)
WITH CHECK (id = auth.uid())
```

Without the `WITH CHECK`, `UPDATE users SET id = <someone else>` would be permitted — the row is visible, so the update proceeds, and the result belongs to another identity. Guarded by `test_user_cannot_reassign_their_profile_to_another_identity`.

The observable difference in failure mode is worth knowing: a `USING` mismatch **affects zero rows silently**, while a `WITH CHECK` violation **raises**. Tests must assert the right one.

### `users` is not tenant-scoped

A user is not owned by a workspace, so its policy asks "which users is this requester entitled to see" rather than filtering on `workspace_id`. Self, plus co-members. Without the co-membership clause a member listing shows nobody but the viewer — which is the feature `email` was denormalized onto `users` for ([[Table - users]]).

That policy queries `workspace_members` directly rather than only through the helper, because it must confirm the *target* user's membership too. No recursion arises: it is a policy on `users`, not on `workspace_members`.

### Liveness belongs in the query, not the policy

**A SELECT policy must not filter `deleted_at IS NULL` on a table anything soft-deletes** — see above for why it makes the soft delete itself impossible.

What still filters, and must: `app_current_user_workspaces()` checks `deleted_at IS NULL` on the caller's *own* membership, so a removed member loses access immediately. That is where liveness is load-bearing for **isolation**; everywhere else it is a question about which rows a caller wants, which the query owns.

Every query on such a table therefore states it explicitly. A listing that inherited the filter from a policy and never said so will start showing soft-deleted rows the moment the policy is corrected.

### DELETE is granted to no one

Deliberately, on every table. Removal is a soft delete — an `UPDATE` setting `deleted_at`, already governed by the UPDATE policies. A `DELETE` policy would create a second, unaudited removal path bypassing soft deletion entirely.

With no DELETE policy present, RLS denies the command by default. **The absence is the control**: a reader who finds no DELETE policy should not conclude one was forgotten.

## `ENABLE` Is Not Enough — Also `FORCE`

```sql
ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.<table> FORCE ROW LEVEL SECURITY;
```

`ENABLE` applies policies to everyone **except the table owner**. Without `FORCE`, the owner (`postgres`) silently bypasses its own policies — which would make an isolation test connecting as the owner pass while proving nothing. Both statements, every table. `test_every_application_table_has_rls_enabled_and_forced` queries the catalog to enforce this on tables added later.

## What RLS Cannot Enforce

> [!danger] `service_role` bypasses RLS and no policy can stop it
> The role behind `SUPABASE_SECRET_KEY` carries `rolbypassrls`. It reads and writes **every row in every table regardless of policy**, and this is not fixable in a migration.
>
> The control is architectural, not technical: **the API must not use the secret key for tenant-scoped queries.** Cross-tenant needs go through an audited service path ([[CLAUDE|CLAUDE.md]] §16 — admin and internal tooling do not bypass RLS), which does not exist yet.

The same applies to `postgres`, which holds both `rolbypassrls` and `rolsuper`.

## The Two Connections

**Resolved by [[STEP-10 Authentication Backend]].** The API uses two database connections, as different roles, and conflating them removes tenant isolation entirely:

| Connection | Role | Bypasses RLS | Used for |
|---|---|---|---|
| `DATABASE_URL` | `postgres` | **Yes** — `rolbypassrls` + `rolsuper` | Alembic migrations only |
| `REQUEST_DATABASE_URL` | `projectone_api` | **No** | Every request |

`projectone_api` is created by migration `d7b95c1f4e08`. Supabase's own `authenticator` was the obvious candidate and was rejected: it is a reserved role that `postgres` cannot alter on managed Supabase (`ALTER ROLE authenticator WITH PASSWORD` fails), and its definition belongs to the platform rather than to this project.

Three attributes carry the weight, and none is a default:

- **`NOBYPASSRLS`** — the entire point. Policies apply.
- **`NOSUPERUSER`** — a superuser bypasses RLS regardless of `NOBYPASSRLS`.
- **`NOINHERIT`** — it is granted `authenticated` but holds none of its privileges until it explicitly `SET ROLE`s. A request path that skipped the role switch therefore reads **nothing** rather than everything: the bug fails closed, loudly, instead of silently serving unfiltered data.

`REQUEST_DATABASE_URL` deliberately has **no fallback** to `DATABASE_URL`. A default that silently reused the privileged connection would turn a forgotten environment variable into total, invisible loss of isolation, so the API refuses to start instead.

### How the claim is set

Per **transaction**, never per connection:

```sql
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', <verified sub>, true);
```

Both revert on commit *and* on rollback, which is what makes connection reuse safe. The session-scoped forms (`SET ROLE`, `set_config(..., false)`) look equivalent and are a cross-tenant breach: the claim outlives the request and the next caller to borrow that pooled connection inherits the previous caller's identity.

> [!warning] This leak was reproduced, not theorised
> During STEP-10, a session-scoped `set_config` left the claim set after its transaction committed. A subsequent session with *no* claim read the previous user's workspace. `test_claim_does_not_leak_between_sessions` guards it permanently — and note that a single-request test cannot catch it, because the first request always looks correct.

`set_config` rather than `SET LOCAL` because `SET` does not accept bind parameters: a user id could only reach it through string interpolation. `set_config` takes it as a parameter, keeping a token-derived value out of the SQL text.

## Grants Are a Second, Independent Gate

A grant decides whether a role may attempt a command; a policy decides which rows it then touches. **Both must be right.**

Until [[STEP-10 Authentication Backend]], RLS was doing all the work: `anon` and `authenticated` held full DML on every table (`arwdDxtm`) and were held back purely by policies matching no rows. One forgotten policy on a future table would have exposed it to an unauthenticated role. Migration `c4f21a86b3de` narrows this:

| Role | After |
|---|---|
| `anon` | **Nothing.** No policy names it, so the grant was pure latent surface. |
| `authenticated` | `SELECT`, `INSERT`, `UPDATE` — exactly the three commands policies exist for. |

`DELETE` is revoked from both, so the grant now agrees with the deliberate absence of a DELETE policy. **`TRUNCATE` matters most**: it is not subject to RLS *at all*, so a role holding it can empty a tenant table regardless of every policy on it.

> [!warning] Revoking the existing tables is not enough
> Supabase ships `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role`, so **every table created from now on** is automatically granted full DML to `anon` and `authenticated` — DELETE and TRUNCATE included. Revoking only today's tables would leave the next tenant table arriving wide open.
>
> This is the same class of defect STEP-09 found with `REVOKE ... FROM PUBLIC` failing to revoke `anon`'s EXECUTE: Supabase's defaults are granted to roles **by name**, so they must be addressed by name. `c4f21a86b3de` alters the default privileges too, and `test_future_tables_do_not_inherit_permissive_grants` creates a real table and inspects what it inherited.
>
> **Known residue:** `supabase_admin` owns a second copy of these defaults that `postgres` cannot alter (it is not a superuser on managed Supabase). That copy governs tables *Supabase* creates, not ProjectOne's, because Alembic connects as `postgres`.

## Adding a New Tenant Table

1. Create the table with `workspace_id uuid NOT NULL` referencing `workspaces(id)`.
2. In the **same migration**: `ENABLE` and `FORCE` row level security.
3. Add SELECT / INSERT / UPDATE policies `TO authenticated` routing through `app_current_user_workspaces()`. No DELETE policy.
4. **Do not filter `deleted_at IS NULL` in the SELECT policy** if anything will ever soft-delete this table — it makes the soft delete impossible, and the refusal names row-level security while pointing at the wrong policy. Filter liveness in the queries instead. Two steps have now been spent on this exact defect.
5. **Grant only what the policies need:** `GRANT SELECT, INSERT, UPDATE ... TO authenticated`, and nothing to `anon`. The corrected default privileges (`c4f21a86b3de`) should already produce this, but state it in the migration rather than depending on it.
6. Reach the table through `TenantConnectionDep` only. A tenant query over the privileged connection has no isolation at all, and nothing about the query will look wrong.
7. Add an isolation test to `apps/api/tests/test_rls_isolation.py` proving a user from workspace A cannot read, update or delete workspace B's rows.
8. Confirm the new test **fails when the policy is removed**. A test that passes either way is asserting nothing.

## Testing

Isolation tests live in `apps/api/tests/test_rls_isolation.py` and run in CI against a throwaway PostgreSQL service container — never the development project, since they write and delete rows.

Two properties make them meaningful rather than decorative:

- **They assert real database behaviour.** A stub proving "our fake returned no rows" says nothing about whether a policy holds. These connect as `authenticated` with a JWT claim set, exactly as a request will.
- **They fail when RLS is off.** Verified during STEP-09: with the policies disabled, 15 of 17 fail. `test_policies_are_what_makes_these_tests_pass` encodes this permanently by disabling RLS mid-test, observing the breach, and restoring it.

`apps/api/tests/test_request_session.py` ([[STEP-10 Authentication Backend]]) covers the gap those tests structurally cannot: they set the role and claim *by hand*, so they prove the policies work without proving the **application** is subject to them. An API connecting as `postgres` would read every workspace's rows while all 17 continued to pass. The STEP-10 tests use the real `RequestSessionFactory` over the real request-path role, and assert `rolbypassrls IS false` on it directly.

CI sets `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, which turns "no database configured" from a skip into a hard failure — otherwise a broken service container would downgrade the security suite to skips while CI still reported green.

Stock PostgreSQL has no `auth.uid()`, so the test harness shims it (`apps/api/tests/conftest.py`). The shim is applied **only when the function is genuinely absent**, so a run against a real Supabase project exercises the platform's own function.

---

## Navigation

- **Previous:** [[Table Conventions]]
- **Next:** [[Schema Overview]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[Schema Overview]] · [[Table - users]] · [[Table - workspaces]] · [[Table - workspace_members]] · [[Authentication and Authorization]] · [[Security Architecture]] · [[Chapter 09 - Security Standards]]
