---
title: "Table - audit_log"
category: Database Table
status: stable
version: "1.1"
last_updated: 2026-08-04
tags: [database, schema, security, multi-tenancy]
table_name: "audit_log"
---

# Table — audit_log

Created by migration `a3c07d5e91f4` ([[STEP-13 Auth Users Workspaces Endpoints]]).

## Purpose

Records **who changed what**, in which workspace, and when. This is the distinction it exists for: [[API Conventions]]'s request logging records that a request happened; it does not record which identity performed a consequential action. [[API Architecture]] has required audit logging since before there was anything to audit, and STEP-13 built the first mutations worth auditing — a tenant boundary being created, a member added or removed, ownership changing hands.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | When the action happened. The only timestamp — see below. |
| `workspace_id` | `uuid` | NOT NULL, FK → `workspaces.id` `ON DELETE RESTRICT` | The workspace the action happened in. |
| `actor_id` | `uuid` | NOT NULL, **no FK** | Who acted. |
| `actor_email` | `text` | — | The actor's address **at the time they acted** — a point-in-time snapshot, not a live join. |
| `action` | `text` | NOT NULL, `ck_audit_log_action_valid` | One of `workspace.created`, `member.added`, `member.removed`, `member.left`, `ownership.transferred`, `provider_key.stored`, `provider_key.revoked`, `budget.updated`. |

| `target_id` | `uuid` | — | Who or what was acted on. Null where the target is the workspace itself. |
| `detail` | `jsonb` | NOT NULL, default `'{}'` | Action-specific context: the role granted, the workspace name at creation. |

**Index:** `ix_audit_log_workspace_id_created_at` on `(workspace_id, created_at DESC)` — serves both the policy's filter and the newest-first sort every audit view wants.

### The three AI settings actions

`provider_key.stored`, `provider_key.revoked` and `budget.updated` were added by migration `c9d3b71e08af` ([[STEP-19 Settings and BYOK UI]]). Storing a provider key authorizes spend against the workspace's own provider account, so its appearance and disappearance are security questions somebody eventually needs answered; a budget ceiling is a decision about money, where "who changed it" is the first question asked after a surprising invoice.

**Neither the key nor its `last_four` is recorded.** An audit row is readable by *every* member, including a plain one, so four characters of a credential in this table would be a leak that took one extra step rather than none. The row names the provider and the actor, and nothing else.

## Two Conventions Deliberately Broken

[[Table Conventions]] gives every table five standard columns and a soft-delete default. This table departs from both, and the departures **are** the security property rather than an oversight.

- **No `deleted_at`, and no soft deletion.** An audit record its own subject can remove is not an audit record. [[CLAUDE|CLAUDE.md]] §16 states it outright: audit logs are retained on their own schedule, independent of user deletion requests, because audit trails exist precisely to survive the events they record.
- **No `version`, and no `touch_row` trigger.** Both exist to track modification, and these rows are never modified. Attaching a version counter would imply an update path that must not exist.

## Immutability Is Enforced Three Ways

A rule this important does not rest on any single mechanism:

1. **No INSERT, UPDATE or DELETE policy.** RLS denies by default, so none of those commands has any route for `authenticated`. The absence *is* the control — a reader finding one policy here should not conclude the rest were forgotten.
2. **Grants match.** `authenticated` holds **SELECT only**. `TRUNCATE` matters most: it is not subject to RLS at all, so a role holding it could empty this table regardless of every policy on it.
3. **Writes come only from the privileged connection**, inside `AuditService`. A client able to write its own audit rows could forge them — worse than having no trail, because a forged trail is trusted.

Asserted directly against the database in `apps/api/tests/test_audit_log.py`.

## Row Level Security

One policy:

```sql
CREATE POLICY audit_log_select_same_workspace ON public.audit_log
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));
```

Routes through the same membership helper as every other tenant table ([[RLS Policy Pattern]]). No `deleted_at IS NULL` filter, because the column does not exist. An audit log readable across tenant boundaries would disclose exactly the actions most worth keeping private.

## Why `actor_id` Is Not a Foreign Key

Deliberate. `users.id` is `RESTRICT`-referenced elsewhere, so an FK here would mean either blocking a user's deletion forever or cascading their audit history away with them. **The trail must outlive the account that generated it.** The actor is therefore a bare uuid plus the denormalised email captured at write time.

`workspace_id` *is* a foreign key, with `RESTRICT`, so a workspace row cannot be hard-deleted out from under its own history. One consequence worth knowing: test teardown must clear this table before deleting workspaces.

## Export and Erasure

Registered in `REGISTERED_STORES` as `AuditLogStore`, and it is **the one store that exports but never erases**:

- **Exportable** — a user is entitled to a copy of the record of what was done in their workspace.
- **Not erasable** — `erase()` returns 0. A workspace erasure reports `"audit_log": 0`, which **discloses** the retention exception rather than hiding it. Omitting the store entirely would be indistinguishable from having forgotten it.

Otherwise anyone holding `DELETE_WORKSPACE` could destroy the evidence of what they did on the way out — the single outcome an audit log exists to prevent.

## Retention

**90 days, then permanent deletion.** Set by the project owner on 2026-08-15 and implemented in [[STEP-25a Foundation Remediation]] (FA-07), closing the unbounded-retention gap [[STEP-25 Foundation Audit and Internal Readiness]] recorded.

- **Configurable, not hard-coded** — `PROJECTONE_AUDIT_RETENTION_DAYS`, so the window can move before public release without a code change ([[CLAUDE|CLAUDE.md]] §28a).
- **Zero means retain indefinitely**, for a deployment under a legal obligation to keep everything. The code refuses to derive a cutoff from it rather than relying on arithmetic: the dangerous misreading of `0` is "keep nothing", and the two differ by the entire audit log.
- **A negative window is rejected at startup** (`ge=0`). It would place the cutoff in the future and expire every existing row — a configuration typo that must fail loudly rather than silently destroy the trail.
- **The purge is a filtered `DELETE`, never `TRUNCATE`**, which would bypass row-level filtering entirely. `AuditRepository.purge_statement()` is exposed as a string precisely so a test can assert the `WHERE` clause exists; once an unfiltered delete has run, the evidence it was wrong is the thing it destroyed.
- **It runs over the privileged connection**, like every other write here — the table has no DELETE policy and `authenticated` holds no DELETE grant, so this is the audited service path [[CLAUDE|CLAUDE.md]] §16 requires, not a bypass.
- **The disclosure is derived from the configured value**, so the sentence users are shown cannot drift from the behaviour.

This is the **bounded** legal exception to erasure that §16 requires, rather than the unbounded one it was.

## Known Gaps
- **Coverage is the STEP-13 mutations only.** Authentication events (sign-in, sign-out, failed attempts) are not recorded here. They are arguably the most security-relevant events of all, and adding them is a deliberate extension rather than an oversight to fix silently.
- **Writes are best-effort.** `AuditService.record` never raises: an audit-write failure must not turn a successful removal into a 500 the caller retries, because the retry performs the action twice. Failures are logged at `exception` level. An action whose audit record must be atomic with it needs a different mechanism.

---

## Navigation

- **Previous:** [[Table - workspace_members]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Schema Overview]] · [[Table Conventions]] · [[RLS Policy Pattern]] · [[API Endpoints]] · [[Table - workspaces]]
