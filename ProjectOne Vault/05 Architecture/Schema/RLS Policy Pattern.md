---
title: RLS Policy Pattern
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-01
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
USING (deleted_at IS NULL AND workspace_id IN (SELECT public.app_current_user_workspaces()))
```

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
| `workspaces` | UPDATE | Live membership required |
| `workspaces` | INSERT | The row must name the creator as `owner_id` |
| `workspace_members` | SELECT | Same workspace |
| `workspace_members` | UPDATE | Same workspace, and cannot be moved to another |
| `workspace_members` | INSERT | Same workspace |

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

### Every policy filters `deleted_at IS NULL`

Membership is soft-deleted, so a removed member's row still exists. A policy that omits this keeps serving them indefinitely — and it fails silently, because everything still looks correct. The partial indexes from `8a6f39b07c12` carry the same predicate, so matching policies stay index-served.

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
> The control is architectural, not technical: **the API must not use the secret key for tenant-scoped queries.** Cross-tenant needs go through an audited service path ([[CLAUDE|CLAUDE.md]] §16 — admin and internal tooling do not bypass RLS), which does not exist yet. [[STEP-10 Authentication Backend]] owns establishing which role the API actually connects as, and it must not be this one.

The same applies to `postgres`, which holds both `rolbypassrls` and `rolsuper` and is what `DATABASE_URL` currently connects as — appropriate for migrations, never for serving requests.

## Adding a New Tenant Table

1. Create the table with `workspace_id uuid NOT NULL` referencing `workspaces(id)`.
2. In the **same migration**: `ENABLE` and `FORCE` row level security.
3. Add SELECT / INSERT / UPDATE policies `TO authenticated` routing through `app_current_user_workspaces()`. No DELETE policy.
4. Filter `deleted_at IS NULL` in every `USING` clause.
5. Add an isolation test to `apps/api/tests/test_rls_isolation.py` proving a user from workspace A cannot read, update or delete workspace B's rows.
6. Confirm the new test **fails when the policy is removed**. A test that passes either way is asserting nothing.

## Testing

Isolation tests live in `apps/api/tests/test_rls_isolation.py` and run in CI against a throwaway PostgreSQL service container — never the development project, since they write and delete rows.

Two properties make them meaningful rather than decorative:

- **They assert real database behaviour.** A stub proving "our fake returned no rows" says nothing about whether a policy holds. These connect as `authenticated` with a JWT claim set, exactly as a request will.
- **They fail when RLS is off.** Verified during STEP-09: with the policies disabled, 15 of 17 fail. `test_policies_are_what_makes_these_tests_pass` encodes this permanently by disabling RLS mid-test, observing the breach, and restoring it.

CI sets `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, which turns "no database configured" from a skip into a hard failure — otherwise a broken service container would downgrade the security suite to skips while CI still reported green.

Stock PostgreSQL has no `auth.uid()`, so the test harness shims it (`apps/api/tests/conftest.py`). The shim is applied **only when the function is genuinely absent**, so a run against a real Supabase project exercises the platform's own function.

---

## Navigation

- **Previous:** [[Table Conventions]]
- **Next:** [[Schema Overview]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[Schema Overview]] · [[Table - users]] · [[Table - workspaces]] · [[Table - workspace_members]] · [[Authentication and Authorization]] · [[Security Architecture]] · [[Chapter 09 - Security Standards]]
