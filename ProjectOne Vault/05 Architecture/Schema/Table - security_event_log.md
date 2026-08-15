---
title: "Table - security_event_log"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-15
tags: [database, schema, security, authentication]
table_name: "security_event_log"
---

# Table — security_event_log

Created by migration `b2e94c17a5d3` ([[STEP-25a Foundation Remediation]], FA-06).

## Purpose

Records **authentication events** — sign-up, sign-in, sign-out and token refresh, succeeded and failed alike. These are the events that precede having a workspace at all, and the ones a breach investigation starts from.

The distinction from [[Table - audit_log]] is the reason both exist: `audit_log` records *who changed what inside a tenant*; this records *who tried to authenticate, and whether it worked*.

## Why a Separate Table

The owner's decision of 2026-08-15, and the constraint that forces it.

`audit_log.workspace_id` is `NOT NULL` with a `RESTRICT` foreign key, because every action it records happens inside a tenant and is read back by that tenant's members. **A failed sign-in has no tenant and no user** — at the moment it is recorded, nothing about the caller is known or trustworthy.

Making `audit_log.workspace_id` nullable would place rows in a tenant-scoped table that `audit_log_select_same_workspace` cannot classify: `workspace_id IN (...)` is neither true nor false for NULL, so such rows would be **invisible to every reader** while still occupying the table a tenant is told is their audit trail. Migration `a3c07d5e91f4` wrote itself out of exactly that — *a nullable tenant column on a tenant-scoped table is a row that no policy can classify* — and this table keeps that decision intact rather than reversing it.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | When it happened. The only timestamp — these rows are never modified. |
| `event_type` | `text` | NOT NULL, `ck_security_event_log_type_valid` | One of `auth.sign_up`, `auth.sign_in`, `auth.sign_out`, `auth.token_refresh`. |
| `outcome` | `text` | NOT NULL, `ck_security_event_log_outcome_valid` | `succeeded` or `failed`. |
| `request_id` | `text` | NOT NULL | The request's correlation id, tying this to the request log without either side carrying the other's data. |
| `user_id` | `uuid` | **nullable**, no FK | Who, where already known to the caller. **Null on every failure.** |
| `workspace_id` | `uuid` | **nullable**, **no FK** | The workspace, on the rare event that has one. |
| `metadata` | `jsonb` | NOT NULL, default `'{}'`, `ck_security_event_log_metadata_bounded` (≤ 2048 bytes) | Bounded, allowlisted diagnostic context — a failure reason, never an identifier. |

**Index:** `ix_security_event_log_created_at` on `(created_at DESC)` — serves both the retention scan and the time-ordered read an investigation wants. Deliberately **no index on `user_id`**: no read path filters by it, and speculative indexing is what [[Chapter 07 - Database Standards]] forbids.

**Two columns are nullable and neither is a foreign key**, both deliberately:

- `user_id` follows `audit_log.actor_id`'s reasoning — the trail must outlive the account, and an FK would mean either blocking a user's deletion forever or cascading their security history away with them.
- `workspace_id` has no FK so this table is **not** a teardown dependant of `workspaces` and cannot block a workspace's deletion on its own security history. It is correctly absent from `conftest._WORKSPACE_DEPENDANTS`, and `test_teardown_completeness` agrees because it queries the live FK graph rather than a second hand-maintained list.

## The Account-Existence Oracle, Closed Four Ways

The hard requirement is not "do not store the password". It is that **an attacker submitting addresses must learn nothing about which ones exist** — and an audit table is a surprisingly easy way to hand that over. Four independent mechanisms, because one would be a single point of failure:

1. **No column can hold a submitted identifier.** No `email`, no `username`, no `identifier` — and deliberately **no `email_hash`**. A hash is an oracle to anyone who can compute it over a guess, which is everyone; it protects the address from a casual reader and not at all from the attack that matters. A test names the forbidden columns, so adding one in good faith fails rather than passes review.
2. **`user_id` is null on every failure**, enforced by `ck_security_event_log_failure_is_anonymous` in the database *and* by `SecurityEvent.__post_init__` in code. A row reading "sign-in failed for user X" answers *does X exist?* from its own contents.
3. **`SecurityEventService.record_failure` has no parameter for an identity.** Not "takes one and discards it" — the parameter does not exist, so a future edit must change the signature and confront why it is shaped this way.
4. **The public response is unchanged.** `sign_in` and `refresh` record and then **re-raise**, leaving the status mapping with `app.core.errors`. Asserted end-to-end: an existing and an unknown account produce identical status and body.

**No IP address is recorded.** Storing one would make this a table of personal data about unauthenticated strangers, failing the data-minimisation rule ([[CLAUDE|CLAUDE.md]] §16) the rest of this schema is built to.

## Immutability Is Enforced Four Ways

1. **No policies at all.** RLS is `ENABLE`d **and** `FORCE`d, and not one policy is defined — so `authenticated` has no route to any command. The total absence *is* the control, and it is **stricter than [[Table - audit_log]]**, which has a SELECT policy because a workspace's own actions are its own business. These events span tenants and precede identity, so there is no correct tenant scope to read them under.
2. **No grants.** `REVOKE ALL` with nothing granted back. A grant is an independent gate from a policy ([[RLS Policy Pattern]]), and `TRUNCATE` in particular is **not subject to RLS at all**.
3. **A `BEFORE UPDATE` trigger that raises.** Policies and grants stop the *request* role; they do not stop the privileged connection the application writes over, and a bug there is precisely what would rewrite history. `security_event_log_forbid_update()` closes that path.
4. **Writes come only from the privileged connection**, inside `SecurityEventService`. A client able to forge its own security events could bury a real one under noise.

`DELETE` is deliberately **not** blocked by the trigger: the approved retention mechanism is a filtered delete, and a trigger forbidding it would make the 90-day policy unimplementable. Deletion is constrained by privilege instead — only the privileged connection can reach the table at all.

Asserted directly against the database in `apps/api/tests/test_security_event_log.py`.

## Row Level Security

**No policies.** RLS denies by default, so this is a complete denial to every non-owner role, and `FORCE` extends it to the owner too.

There is **no tenant-facing read path and no public API endpoint**, by the owner's explicit requirement. An events table spanning tenants has no correct tenant scope to be read under, and inventing one would be the disclosure this design exists to prevent.

## Retention

**90 days, then permanent deletion** — the same window and the same setting (`PROJECTONE_AUDIT_RETENTION_DAYS`) as [[Table - audit_log]]. Sharing the setting is deliberate: these are two halves of one retention commitment, and letting them drift would make the disclosure users are shown true of only one table.

- **Zero means retain indefinitely**, never "keep nothing" — the dangerous misreading differs from the correct one by the entire log.
- **The purge is a filtered `DELETE`, never `TRUNCATE`.** `SecurityEventRepository.purge_statement()` is exposed as a string precisely so a test can assert the `WHERE` clause exists.
- **Boundary tested both directions** — a 91-day row is deleted; 89-day and 1-day rows are kept.

## Known Gaps

- **Coverage is the four endpoints that exist.** Password reset, email change and MFA are not covered because they are not built; each will need its own event type and a widened CHECK constraint.
- **Writes are best-effort.** `SecurityEventService.record` never raises, for the same reason `AuditService.record` does not: a write failure must not turn a successful sign-in into a 500 the caller retries. The trade-off is sharper here — the events most likely to coincide with a write failure are the ones during an incident — so failures log at `exception` level and are alertable.
- **Nothing schedules the purge yet.** The mechanism and its boundary behaviour are proven; wiring it to a scheduler is deployment work belonging with the infrastructure it runs on.

---

## Navigation

- **Previous:** [[Table - audit_log]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Schema Overview]] · [[Table Conventions]] · [[RLS Policy Pattern]] · [[Table - audit_log]] · [[Authentication and Authorization]]
