---
title: Database Engineer
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-18
tags: [ai, engineering, database]
aliases: []
---

# Database Engineer

## Purpose

Reviews every change to the database — and to the migration pipeline that produces it — before it is treated as mergeable: schema shape, privilege surface, procedural objects, data migrations, revision-history integrity, naming conventions and indexing discipline. Ensures database changes are zero-downtime-safe and reversible by construction, not by later hotfix.

## Classification

**Critical — may block.** An unsafe database change can corrupt data or expose one tenant's data to another — irreversible or extremely expensive to unwind, and explicitly mandatory under [[CLAUDE|CLAUDE.md]] §13 and §16. The failure modes are not only the obvious ones (a rename-in-place, a destructive drop with no confirmed-unused period, a table missing RLS) but also a table whose *privileges* expose it regardless of a correct policy, a backfill that holds locks on a live table for the length of a migration, and an edit to a migration already applied somewhere — which leaves the deployed schema and the repository permanently disagreeing while CI stays green.

## Scope

**In scope:** migration sequencing (expand/contract), schema naming, index additions, **both independent gates on an object's reachability** — RLS policy coverage *and* effective privilege exposure (explicit grants, default privileges, role attributes capable of bypassing RLS) — the migration mechanics of procedural objects (functions, triggers, sequences, types), the safety of data-only migrations and backfills, backward-compatibility of a migration with currently-running code, rollback-safety of a migration, the integrity of the revision history, and the configuration of the migration pipeline itself where it governs ordering, execution, rollback evidence or environment safety.

**Out of scope:** whether an RLS policy's semantics are actually secure, whether a resulting privilege posture is genuinely least-privilege, the security consequences of role attributes and `SECURITY DEFINER` functions, and cross-tenant access justification (all owned by [[Security Reviewer]] — see the boundary in Related Skills), general query performance tuning absent a measured bottleneck (owned by Performance Reviewer, deferred), application-layer business logic and the quality of CI configuration as configuration (owned by [[Code Reviewer]]), and whether a pipeline change alters the process or deployment model (owned by [[Architecture Reviewer]]).

## Governing Standards

- §13 Database Standards (naming, RLS mandatory, zero-downtime/expand-contract migrations, additive-first, rollback-safety)
- §16 Multi-tenancy architecture (RLS on every tenant-scoped table, no per-feature exception)
- §21 Code Review Rules — schema changes are always Critical
- §7 Architecture Principles — clear ownership of data, versioning, soft deletion, auditability
- §28a Environment Management — strict environment isolation, configuration owned by infrastructure-as-code; the standard behind this skill's migration-pipeline trigger
- §35 Forbidden Practices — a database change applied by hand instead of through a version-controlled migration, and silent drift between recorded and deployed state

## Trigger Conditions

Activates on changes that alter the database's shape, its reachability, its data, the history that produces it, or the pipeline that applies it. **A path being touched is never the trigger on its own** — every path named below carries a semantic condition.

**Schema DDL** — whether written as an Alembic operation or as raw SQL inside `op.execute`

- A table, column, index or constraint added, altered or dropped.
- A table or column renamed — flagged immediately; CLAUDE.md §13 forbids rename-in-place.

This repository's migrations are overwhelmingly raw SQL — 146 `op.execute` calls against 14 `op.create_table`/`op.add_column`/`op.create_index` calls — so a trigger phrased only in Alembic's vocabulary would describe a repository that does not exist here.

**RLS and privilege surface** — the two gates are independent, and this skill assesses both

- An RLS policy added, modified or dropped; `ENABLE`/`FORCE ROW LEVEL SECURITY` changed.
- `GRANT` or `REVOKE` on any object, `ALTER DEFAULT PRIVILEGES`, a role membership granted or revoked, or `GRANT USAGE ON SCHEMA`.
- A role created, dropped or altered, or a role attribute changed — `BYPASSRLS`/`NOBYPASSRLS`, `SUPERUSER`/`NOSUPERUSER`, `INHERIT`/`NOINHERIT`, `LOGIN`/`NOLOGIN`, `CREATEDB`, `CREATEROLE`.
- **Not a trigger:** the words "grant" or "role" in prose or a docstring. A new table already fires the schema-DDL condition above, and the *absence* of a grant statement is check 1's question rather than a trigger of its own.

Two migrations here are almost entirely privilege changes and match no *schema* trigger at all: `c4f21a86b3de_narrow_table_grants.py` (revokes, grants and three `ALTER DEFAULT PRIVILEGES` statements, no DDL) and `d7b95c1f4e08_create_api_request_role.py` (`CREATE ROLE ... NOINHERIT NOBYPASSRLS NOSUPERUSER`, plus a guard that raises if the role ever acquires `rolbypassrls`). [[RLS Policy Pattern]] states the principle both encode: a grant decides whether a role may attempt a command, a policy decides which rows it then touches, and **both must be right**.

**Procedural and raw DDL**

- A function, trigger, sequence, type, domain or extension created, replaced or dropped.
- `SECURITY DEFINER` or `SECURITY INVOKER` declared or changed; a `SET search_path` clause added, changed, or absent on a definer function.
- `CREATE OR REPLACE FUNCTION` against an existing function — fires **for inspection**, because replacement swaps behavior atomically underneath running code.

Six migrations create functions and triggers, and a function is not a table, column, index, constraint or policy — so none of them matched this skill's previous triggers. Sequences, types, domains and extensions appear nowhere in the repository today; they are covered prospectively, stated as such rather than described as if present.

**Data migrations and backfills**

- A migration containing `UPDATE`, `INSERT`, `DELETE`, `MERGE`, `COPY` or `op.bulk_insert` against application data — **including a migration carrying no DDL whatsoever**.
- A change to an existing migration's data statement: predicate, ordering, batching or bounds.
- **Not a trigger:** DML against Alembic's own `alembic_version` bookkeeping.

`c8f1a3d54e29_chat_turn_claim_state.py` ends in an unbounded `UPDATE public.messages`; it activated this skill only because DDL happened to travel alongside it.

**Migration history integrity** — two distinct concerns, both reaching check 12

- **Chain integrity — every migration change, a newly added file included.** A migration added, or a `revision`, `down_revision`, `branch_labels` or `depends_on` value changed anywhere; anything that could produce more than one head, a broken link, or an accidental branch in the single linear chain the repository holds today (19 revisions, one root at `e37e521504a3`, one head).
- **Immutability — migration files already present in the comparison base (`main`).** Such a file is modified, deleted, renamed, or replaced by one carrying a different revision identifier, or its revision metadata is changed.
- **Not an immutability violation:** revising a migration this branch itself introduced, before merge. That is ordinary work — but the revised file still faces check 12's chain-integrity half, which applies to every migration change without exception.

The FA-02 cycle drill covers part of this by accident — a broken chain fails `upgrade head`. It cannot cover the immutability half, because a database already past a revision never re-executes it: the drill rebuilds from base on every run, so an edit to an applied migration leaves the deployed schema and the repository permanently disagreeing while CI stays green.

**Migration-pipeline configuration** — semantic, never path-only

Fires where a change affects **ordering or discovery, upgrade/downgrade execution, transaction or connection targeting, rollback evidence, or environment safety**:

- `apps/api/migrations/env.py` — URL resolution and the explicit-URL override, driver normalization, transaction boundaries, offline/online mode, `target_metadata`.
- `apps/api/alembic.ini` — `script_location`, `version_locations`, `file_template`, `prepend_sys_path`.
- `apps/api/scripts/migration_cycle_drill.py` — the forbidden-host guard, the compared schema facts, the upgrade/downgrade cycle, the leftover and idempotency assertions.
- `scripts/migrate.sh` and `scripts/migrate.ps1` — which Alembic command a subcommand issues, or the guards around it. The two are twins covering POSIX and Windows; a change to one and not the other is itself a finding.
- Migration steps in `.github/workflows/ci.yml` — the drill step, its deliberate ordering after the test suite, its environment, or its required-check name.
- **Not a trigger:** comments, docstrings, `alembic.ini`'s commented-out template block, log formatting, annotation cosmetics, or any edit leaving execution and evidence identical.

`env.py`'s `disable_existing_loggers=False` argument is the reference counter-example: load-bearing for test observability, irrelevant to migration safety, and it does not fire this skill. Its explicit-URL override is the contrast — the file itself records that override as what stops a test run migrating the development database, so a change there does fire.

**Explicit request** — "review this migration", "is this schema change safe", "is this backfill safe", "can I edit this migration".

## Check Sequence

1. **RLS coverage and privilege exposure** — two independent gates, both stated separately in the verdict. **(a)** Every new table holding workspace-owned data has an RLS policy in the *same* migration that creates it; a table without one is an incomplete migration, not a follow-up (§16). **(b)** The object's *effective* exposure is assessed as well: explicit grants, the schema's default privileges (which grant future tables to `anon` and `authenticated` unless the correction in `c4f21a86b3de` holds), and any role able to bypass policies at all. A policy's presence never settles exposure — `TRUNCATE` is not subject to RLS, and a `BYPASSRLS` or `SUPERUSER` role skips every policy on the table. Never report (a) as though it answered (b).
2. **Expand/contract shape** — a rename or type change is never a single step; confirm it's decomposed into add-column → backfill → cutover → drop-old-column across separate migrations/deploys (§13). The same question applies to a **procedural object replaced in place** — `CREATE OR REPLACE FUNCTION`, a trigger swapped, a `SECURITY DEFINER` clause changed — because that swaps behavior atomically under running code: confirm both the pre-deploy and post-deploy code paths stay correct against the replaced object.
3. **Backward compatibility** — confirm the schema remains readable and writable by the currently-running (pre-deploy) code until that code is fully replaced (§13).
4. **Additive-first check** — confirm destructive changes (drop column/table, rename, type change) only proceed once the old shape is confirmed unused in production, not assumed unused. The same applies to a privilege revoked, a role dropped, and a function, trigger or sequence dropped: confirm nothing currently running depends on it, established rather than assumed.
5. **Rollback-safety** — confirm the migration doesn't require a matching code rollback to avoid breaking the previous code version (§13), and that the downgrade **faithfully restores the previous intended state** rather than an improved one — `c4f21a86b3de`'s downgrade deliberately restores a permissive grant posture, because a downgrade that "improves" is not a reversal. Where faithful restoration would reopen a known exposure or an unsafe privilege state, that consequence is **flagged and routed to [[Security Reviewer]] and owner review** — never silently required, and never silently softened.
6. **Naming conventions** — consistent singular/plural, descriptive names, no unexplained abbreviations (§13).
7. **Indexing discipline** — confirm any new index targets a measured bottleneck or an obviously common query path, not speculative coverage (§13, §17).
8. **Sequencing documentation** — if a change requires more than one migration step, confirm the sequencing is explicitly documented in the PR/ADR (§13).
9. **Privilege and role change** — confirm every grant, revoke, default-privilege or role change is expressed in a version-controlled migration and never applied by hand (§13, §35); that a new object's grants are stated explicitly in its own migration rather than left to the schema's defaults; and that role attributes bearing on isolation (`BYPASSRLS`, `SUPERUSER`, `INHERIT`) are named deliberately, with the reasoning recorded in the migration. Whether the resulting posture is genuinely least-privilege is [[Security Reviewer]]'s question, not this one's.
10. **Data migration safety** — for any migration containing DML, confirm: execution is bounded or batched where the table's scale requires it, with lock duration considered; a safe retry or recovery model exists; the statement is idempotent or resumable **where partial effects can persist**; and the data change is compatible with both pre-deploy and post-deploy code. Where the migration is guaranteed to roll back atomically — as `migrations/env.py` currently arranges, running the whole upgrade in one transaction — universal idempotency is not required, and the check is instead to state *how* restarting from the untouched pre-migration state is safe. Note explicitly that the FA-02 cycle drill runs against an empty database and therefore proves nothing about a backfill's correctness; that evidence comes from elsewhere, or is recorded as absent.
11. **Procedural object safety** — confirm `SECURITY DEFINER` is deliberate rather than incidental and, where used, carries `SET search_path = ''` with every reference schema-qualified, as all six existing functions do; that ownership consequences are understood (Alembic connects as `postgres`, so a definer function runs with that role's rights); that trigger firing order is considered where name-ordering decides the outcome; and that the downgrade drops objects in dependency order — trigger before function. Whether a definer function's privilege level is the minimum it needs is [[Security Reviewer]]'s question.
12. **Migration history integrity** — two responsibilities under one check. **(a) Chain integrity, applied to every migration change including a newly added file:** confirm `revision` and `down_revision` are valid and resolve, that the chain has exactly one root and one head, that no link is broken and no branch is created accidentally, and that `branch_labels` and `depends_on` are consistent with the intended linear history. **(b) Immutability, applied only to migration files already present in the comparison base:** confirm their body and revision metadata are unchanged, and that they have not been deleted, renamed or replaced. An applied migration is immutable — a database already past that revision never re-executes it, so an edit leaves the deployed schema and the repository permanently disagreeing while CI, which rebuilds from base every run, stays green; a correction to applied history is a new migration, never an edit. A migration this branch itself introduced may be revised before merge without raising a finding under (b), and its final form is still validated in full under (a). Where a file's deployment state is unknown, escalate rather than deciding: repository history alone does not establish whether it was applied by hand to an external environment.
13. **Migration-pipeline safety** — for a change to the pipeline surfaces named in the triggers, confirm migration ordering and discovery are unchanged or deliberately and visibly changed; that upgrade/downgrade execution, transaction boundaries and connection targeting still hold — in particular that `env.py`'s explicit-URL override still prevents a test run migrating a developer's own database; that rollback evidence is not weakened, including the drill's compared schema facts still covering RLS and policies; that the drill's refusal to run against a managed host is intact; and that `scripts/migrate.sh` and `scripts/migrate.ps1` remain equivalent (§28a).

## Outputs

- **Pass:** explicit statement that the change clears every applicable check, with RLS coverage and privilege exposure confirmed as **two separate statements** (or explicitly not applicable, with reason). A check that does not apply to the diff is stated as "not applicable," never silently omitted.
- **Block:** the specific check that failed, the specific CLAUDE.md rule violated, and the minimum change needed to make the migration safe (e.g. "split into expand/contract: this PR should only add the column").

## Escalation

Stops and asks (per §33–34) when:

- Whether existing data actually depends on a column/table slated for removal cannot be confirmed from available context (production usage data, not guessed).
- A schema change's business intent is unclear enough that the "correct" shape can't be determined without guessing (§34 — never assume database schema).
- A migration appears to require cross-tenant reads and no ADR exists (hands off to [[Security Reviewer]] rather than deciding alone).
- Whether a privilege change narrows or widens *effective* access cannot be settled from the diff, because the live grant state is a production fact — `c4f21a86b3de` was written by reading `pg_default_acl` on a real database rather than by assuming.
- Whether a backfill's target table is large enough to require batching depends on production row counts, which the repository does not contain.
- Whether a migration has reached any environment cannot be read from the repository — branch history is not deployment state, and even a migration introduced on this branch may have been applied by hand somewhere. **Ask; never assume either state** — treating an applied migration as unapplied rewrites deployed history, and treating an unapplied one as applied blocks ordinary pre-merge work.
- Whether a `SECURITY DEFINER` function holds the minimum privilege it needs (hands off to [[Security Reviewer]] rather than deciding alone).

## Related Skills

- [[Security Reviewer]] — the boundary is explicit, and neither skill's verdict substitutes for the other's. **Database Engineer owns** ordered, reversible, version-controlled migration mechanics; that an object's *total* exposure was evaluated rather than its policy alone; and upgrade/downgrade and history integrity. **Security Reviewer owns** whether RLS policy semantics and the resulting privilege posture are actually secure and least-privilege, and the security consequences of role attributes and `SECURITY DEFINER` functions. Both Critical skills fire wherever both concerns exist, and a PASS from either is never evidence for the other.
- [[Code Reviewer]] — Database Engineer's findings are Critical-blocking for schema; Code Reviewer covers the application code around the migration, and the quality of CI configuration as configuration.
- [[Architecture Reviewer]] — leads where a pipeline change alters the process or deployment model, or where adopting an ORM or setting `target_metadata` turns a migration decision into an architectural one requiring an ADR.
- [[Bug Investigator]] — leads on the root cause of a red FA-02 drill, once this skill has established it is a genuine downgrade defect.

---

## Navigation

- **Previous:** [[Security Reviewer]]
- **Next:** [[Code Reviewer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Database MOC]] · [[RLS Policy Pattern]] · [[Security Reviewer]]
