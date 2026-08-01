---
title: STEP-11a Membership Removal Policy
category: Development/Build Step
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [engineering, workflow, build-step, security, multi-tenancy, database]
step_id: STEP-11a
step_status: Done
detail_level: full
---

# STEP-11a — Membership Removal Policy

**Status:** Done
**Detail level:** full — inserted between [[STEP-11 Authorization and RBAC]] and [[STEP-12 API Conventions and Middleware]] by owner decision on 2026-08-01.

## Why This Step Exists

[[STEP-11 Authorization and RBAC]] found that **soft-deleting a `workspace_members` row is impossible for every role, including `owner`** — STEP-09's `workspace_members_select_same_workspace` filters `deleted_at IS NULL`, so the row becomes invisible to the statement writing it and PostgreSQL rejects the `UPDATE`. Leaving a workspace and removing a member both had no working path.

Fixing it required a Critical multi-tenancy decision and the business rules that go with it ([[CLAUDE|CLAUDE.md]] §21). **The project owner supplied both on 2026-08-01**, which is what unblocks this work.

It is its own step rather than part of [[STEP-12 API Conventions and Middleware]] because it is an RLS and membership change, not an API convention — folding it into a middleware step would put a Critical multi-tenancy change where no reviewer would look for it ([[CLAUDE|CLAUDE.md]] §29/§35).

## Goal

Removal and departure work, governed by the owner's rules, enforced in the database rather than by application discipline alone.

## The Rules (owner-supplied, 2026-08-01)

| # | Rule |
|---|---|
| 1 | The last owner may never leave or be removed. |
| 2 | An owner may remove admins and members. |
| 3 | An owner may transfer ownership before leaving. |
| 4 | An admin may remove members only. |
| 5 | A member may only leave the workspace themselves. |

Rule 1 is a **table-level invariant**, not a row predicate — it depends on how many live owners remain, which no RLS `USING` clause can count without recursing on `workspace_members`. It needs a trigger. The rest are row-level and belong in the policy.

Rule 2 and 4 together mean removal rights are **strictly ranked**: owner > admin > member. An admin removing another admin is denied, which rule 4 states by omission and this step must state explicitly.

## Scope

Database enforcement plus the service layer above it, matching [[Authorization Model]]'s established split. **No UI, and no membership endpoints** — [[STEP-13 Auth Users Workspaces Endpoints]] owns those and is what consumes this.

## Prerequisites

- [[STEP-11 Authorization and RBAC]] — `Done`, owner-approved 2026-08-01

## Required Documentation

- [[RLS Policy Pattern]] — the SELECT policy being changed, and the migration shape to follow
- [[Authorization Model]] — the enforcement split and the permission matrix this extends

## Tasks

1. **Unblock the soft delete.** Change `workspace_members_select_same_workspace` so a row being soft-deleted remains visible to the statement writing it. Establish and document what this means for read paths — every existing query filtering `deleted_at IS NULL` explicitly must keep behaving identically.
2. **Express rules 2, 4 and 5 in the UPDATE policy.** Removal rights ranked owner > admin > member; a member may soft-delete only their own row. An admin removing an admin or an owner is denied.
3. **Enforce rule 1 with a trigger**, because it is a table-level invariant. The last live owner cannot be soft-deleted and cannot be demoted — demotion is the same hole by another route.
4. **Implement ownership transfer** (rule 3) as an atomic operation: promote the successor and demote the departing owner in one transaction, never leaving the workspace ownerless in between.
5. **Add the permissions and service layer** above the policies, following [[Authorization Model]] — `REMOVE_MEMBER`, `LEAVE_WORKSPACE`, `TRANSFER_OWNERSHIP` in the matrix, decided in a service, surfaced as 403.
6. **Resolve `WorkspaceMembersStore.erase`**, which returns 0 today because erasure was impossible.

## Validation

- Each of the five rules tested **in both directions** — permitted for the role that holds it, denied for the one that does not. A check denying everything passes a one-sided test.
- The last owner cannot leave, cannot be removed, and cannot be demoted. All three, because they are three routes to the same broken state.
- An admin cannot remove another admin or an owner.
- Ownership transfer leaves exactly one owner, and the workspace is never ownerless mid-transaction.
- The STEP-09, STEP-10 and STEP-11 suites all still pass — in particular the isolation tests, since this step **widens** a SELECT policy and must not have widened it across the tenant boundary.
- The new tests fail when the new predicates are removed ([[RLS Policy Pattern#Testing]]).
- `test_self_removal_is_blocked_by_the_step_09_select_policy` is **deleted**, not adjusted — it pinned a limitation that no longer exists.
- Lint, format, type-check and the full suite pass in CI.

## Definition of Done

The five rules are enforced in the database and honoured by the service layer; removal, departure and ownership transfer all work; a workspace can never be left ownerless; and tenant isolation is provably unchanged.

**Critical change** ([[CLAUDE|CLAUDE.md]] §21 — authorization, security controls, multi-tenancy/RLS): flag for owner review.

## Outcome

**Removal, departure and ownership transfer all work.** Migration `b8e1d94c50a7` carries the database half; `MembershipService` carries the service half. The model is documented in [[Authorization Model]] and the policy detail in [[RLS Policy Pattern]]; neither is restated here.

### How each rule is enforced

| Rule | Mechanism |
|---|---|
| 1. Last owner may never leave or be removed | `trg_workspace_members_protect_last_owner`, closing **both** removal and demotion |
| 2. Owner may remove admins and members | Ranked `USING` clause via `app_workspace_role()` |
| 3. Owner may transfer ownership before leaving | `WITH CHECK` — only an owner may create an owner; transfer is atomic |
| 4. Admin may remove members only | The same ranked clause, strict `>` |
| 5. Member may only leave themselves | The policy's own-row branch |

### Three decisions worth recording

1. **The `deleted_at` filter moved out of the SELECT policy into the queries.** A policy answers "whose rows may this caller touch" — a tenant question that `deleted_at` has nothing to do with. This is the narrowest available fix and it does not weaken isolation: `app_current_user_workspaces()` still filters on the caller's own membership, so a removed member still loses access immediately.
2. **Rule 1 is a trigger, not a policy.** It depends on how many owners remain *after* the statement, which would mean counting `workspace_members` from inside a policy on `workspace_members` — the recursion STEP-09's helper exists to break. `DEFERRABLE INITIALLY IMMEDIATE`, so ownership transfer works in either statement order.
3. **`LastOwnerError` is a 409, not a 403,** and deliberately not an `AuthorizationError` subclass. An owner leaving holds `LEAVE_WORKSPACE`; what refuses them is the workspace's state. A 403 would send them looking for a permission problem that does not exist.

### Found while building

- **Demotion is a second route to an ownerless workspace**, and a guard watching only `deleted_at` would miss it entirely — an owner could rename themselves `member` with every row still live. Both transitions are covered, and tested separately.
- **A STEP-09 test had to be re-based.** `test_soft_deleted_membership_loses_access` removed the sole owner's membership to prove removed members lose access. Under rule 1 that is now forbidden, so it removes a non-last-owner instead — the property it asserts is unchanged, and it now asserts the removed member lost *that* workspace rather than seeing nothing at all.
- **`WorkspaceMembersStore.erase` excludes the actor's own row.** They are necessarily an owner to have reached it, and the last-owner trigger would otherwise refuse the statement and fail the whole erasure. It returned a hardcoded 0 before this step.

### Validation

Run against a real PostgreSQL — a throwaway database on the development Supabase instance, created and dropped for the run, with the genuine `auth.uid()`. **133 passed, 0 failed**; lint, format and `mypy app` clean. The STEP-09, STEP-10 and STEP-11 suites all still pass, which matters more than usual here because this step *widened* a SELECT policy: `test_the_select_policy_still_blocks_the_other_tenant` proves the widening stopped at the workspace boundary.

`test_the_trigger_is_what_pins_the_last_owner` disables the trigger, demonstrates the workspace can then be orphaned, and restores it — so the rule 1 tests cannot pass for an unrelated reason.

### Deliberately not done

- **Membership endpoints.** [[STEP-13 Auth Users Workspaces Endpoints]] owns the HTTP surface; this step stopped at the service, which is why it has no router changes.
- **Inviting members.** Still blocked by the INSERT policy, and still needs the audited service path STEP-13 owns.
- **Hard deletion.** Removal remains a soft delete; the scheduled purge is a later concern.

---

## Navigation

- **Previous:** [[STEP-11 Authorization and RBAC]]
- **Next:** [[STEP-12 API Conventions and Middleware]]
- **Parent:** [[Build Plan]]
