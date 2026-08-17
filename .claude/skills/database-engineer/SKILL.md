---
name: database-engineer
description: Reviews changes to the database and to the migration pipeline that produces it. Triggers on schema DDL (tables, columns, indexes, constraints) written as Alembic operations or as raw SQL; on RLS policies; on privilege changes — grants, revokes, default privileges, role creation, and role attributes including BYPASSRLS/NOBYPASSRLS and INHERIT/NOINHERIT; on procedural objects — functions, triggers, sequences, types, and SECURITY DEFINER/INVOKER declarations; on data-only migrations and backfills carrying no DDL at all; on migration-history integrity — chain validity (revision/down_revision resolving, one root and one head, no accidental branch) on any migration change including newly added files, and immutability of migration files already present in the base branch, which must not be modified, deleted, renamed or replaced; and on migration-pipeline configuration (migrations/env.py, alembic.ini, migration_cycle_drill.py, scripts/migrate.sh and migrate.ps1, migration CI steps) where the change affects ordering, discovery, upgrade/downgrade execution, connection targeting, rollback evidence or environment safety — but not on prose or mechanical edits to those files. Critical — may block the change.
classification: critical
---

# Database Engineer

Source of truth: `ProjectOne Vault/06 AI/Skills/Database Engineer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Path alone never fires this skill; every condition below is semantic. Migrations here are mostly raw SQL inside `op.execute` — match the SQL, not only Alembic operations.

**Schema DDL**
- Table, column, index or constraint added, altered or dropped.
- Table or column renamed.

**RLS and privilege surface**
- RLS policy added/modified/dropped; `ENABLE`/`FORCE ROW LEVEL SECURITY` changed.
- `GRANT`/`REVOKE` on any object, `ALTER DEFAULT PRIVILEGES`, role membership granted/revoked, `GRANT USAGE ON SCHEMA`.
- Role created/dropped/altered, or a role attribute changed: `BYPASSRLS`, `SUPERUSER`, `INHERIT`, `LOGIN`, `CREATEDB`, `CREATEROLE`, and their negations.
- **Not a trigger:** "grant"/"role" in prose or a docstring. A new table fires the schema-DDL condition; a *missing* grant statement is check 1's question, not a trigger.

**Procedural and raw DDL**
- Function, trigger, sequence, type, domain or extension created, replaced or dropped.
- `SECURITY DEFINER`/`SECURITY INVOKER` declared or changed; `SET search_path` added, changed, or absent on a definer function.
- `CREATE OR REPLACE FUNCTION` on an existing function — fires for inspection.

**Data migrations and backfills**
- Migration contains `UPDATE`, `INSERT`, `DELETE`, `MERGE`, `COPY` or `op.bulk_insert` against application data — including a migration with no DDL at all.
- An existing migration's data statement changes predicate, ordering, batching or bounds.
- **Not a trigger:** DML against `alembic_version`.

**Migration history integrity** — two concerns, both reaching check 12
- **Chain integrity (any migration change, new files included):** a migration added, or `revision`/`down_revision`/`branch_labels`/`depends_on` changed anywhere; anything that could create multiple heads, a broken link, or an accidental branch.
- **Immutability (files present in the comparison base `main` only):** such a file modified, deleted, renamed, replaced with a different revision id, or its revision metadata changed.
- **Not an immutability violation:** revising a migration this branch introduced, before merge — its final form still faces check 12(a).

**Migration-pipeline configuration** — fires only where ordering/discovery, upgrade/downgrade execution, transaction or connection targeting, rollback evidence, or environment safety changes:
- `apps/api/migrations/env.py`, `apps/api/alembic.ini`
- `apps/api/scripts/migration_cycle_drill.py`
- `scripts/migrate.sh` and `scripts/migrate.ps1` — twins; one changed without the other is itself a finding.
- migration steps in `.github/workflows/ci.yml`
- **Not a trigger:** comments, docstrings, commented-out ini blocks, log formatting, annotation cosmetics, or any edit leaving execution and evidence identical.

**Explicit request** — "review this migration", "is this schema change safe", "is this backfill safe", "can I edit this migration".

## Check Sequence

Run in order; stop and report immediately on the first Critical finding rather than continuing silently past it. A check that does not apply is stated as "not applicable," never omitted:

1. **RLS coverage and privilege exposure** — two independent gates, reported separately. (a) every new tenant-owned table has an RLS policy in the same migration that creates it. (b) effective exposure assessed: explicit grants, the schema's default privileges, and any role able to bypass policies (`BYPASSRLS`, `SUPERUSER`). `TRUNCATE` is not subject to RLS. Never let (a) stand as the answer to (b).
2. **Expand/contract shape** — a rename or type change is decomposed into add-column → backfill → cutover → drop-old-column across separate migrations/deploys, never one step. A procedural object replaced in place (`CREATE OR REPLACE FUNCTION`, a trigger swap, a `SECURITY DEFINER` change) raises the same question: pre-deploy and post-deploy code both stay correct against it.
3. **Backward compatibility** — schema stays readable/writable by the currently-running pre-deploy code throughout rollout.
4. **Additive-first** — destructive changes (drop column/table, rename, type change) proceed only once the old shape is confirmed unused in production; the same for a privilege revoked, a role dropped, or a function/trigger/sequence dropped.
5. **Rollback-safety** — the migration doesn't require a matching code rollback to avoid breaking the previous code version, and the downgrade faithfully restores the previous *intended* state rather than an improved one. Where faithful restoration would reopen a known exposure or unsafe privilege state, flag it and route to `security-reviewer` and owner review — never silently require it, never silently soften it.
6. **Naming conventions** — consistent singular/plural, descriptive, no unexplained abbreviations.
7. **Indexing discipline** — new indexes target a measured bottleneck or an obviously common query path, not speculative coverage.
8. **Sequencing documentation** — multi-step migrations have their sequencing explicitly documented in the PR/ADR.
9. **Privilege and role change** — expressed in a version-controlled migration, never applied by hand; a new object's grants stated explicitly rather than left to schema defaults; isolation-bearing role attributes (`BYPASSRLS`, `SUPERUSER`, `INHERIT`) named deliberately with the reasoning recorded. Whether the posture is least-privilege → `security-reviewer`.
10. **Data migration safety** — bounded or batched where the table's scale requires it, with lock duration considered; a safe retry or recovery model exists; idempotent or resumable **where partial effects can persist**; compatible with pre-deploy and post-deploy code. Where the run rolls back atomically (`migrations/env.py` runs the upgrade in one transaction), do not demand idempotency — state instead how restarting from the untouched pre-migration state is safe. The FA-02 drill runs against an empty database and proves nothing about a backfill.
11. **Procedural object safety** — `SECURITY DEFINER` deliberate and carrying `SET search_path = ''` with schema-qualified references; ownership consequences understood (Alembic connects as `postgres`); trigger firing order considered where name order decides it; downgrade drops in dependency order, trigger before function. Whether the privilege level is minimal → `security-reviewer`.
12. **Migration history integrity** — (a) **chain integrity, every migration change including newly added files:** `revision`/`down_revision` valid and resolving, one root, one head, no broken link, no accidental branch, `branch_labels`/`depends_on` consistent with the intended linear history. (b) **immutability, base-present files only:** body and revision metadata unchanged; not deleted, renamed or replaced. A correction to applied history is a new migration, never an edit. A migration introduced by this branch may be revised before merge without a finding under (b), and is still validated in full under (a). Deployment state unknown → escalate: repository history does not prove whether a file was applied by hand elsewhere.
13. **Migration-pipeline safety** — ordering and discovery unchanged or deliberately changed; execution, transaction boundaries and connection targeting still hold, including `env.py`'s explicit-URL override; rollback evidence not weakened (the drill's compared schema facts still cover RLS and policies); the drill's managed-host refusal intact; `scripts/migrate.sh` and `scripts/migrate.ps1` still equivalent.

## Output Format

**PASS** — one line per check confirming it was evaluated and cleared, or "not applicable to this diff." Check 1 produces **two** lines — RLS coverage, and privilege exposure — and neither stands for the other.

**BLOCK** — for each failed check: the check name, the specific CLAUDE.md section violated (cite §number), and the minimum change needed (e.g. "split into expand/contract: this PR should only add the column").

## Escalation

Stop and ask rather than deciding when:
- Whether existing data still depends on a column/table slated for removal can't be confirmed.
- A schema change's business intent is unclear enough that the correct shape can't be determined without guessing.
- A migration appears to need cross-tenant reads with no ADR — hand off to `security-reviewer` rather than deciding alone.
- Whether a privilege change narrows or widens effective access can't be settled from the diff — the live grant state is a production fact.
- Whether a backfill's target table is large enough to require batching depends on production row counts.
- Whether a migration has reached any environment cannot be read from the repository — branch history is not deployment state. Ask; never assume either state.
- Whether a `SECURITY DEFINER` function holds the minimum privilege it needs — hand off to `security-reviewer`.

## Handoff

- RLS policy *semantics*, least-privilege adequacy of a resulting posture, security consequences of role attributes and `SECURITY DEFINER` functions, cross-tenant justification → `security-reviewer` skill. This skill owns migration mechanics, total-exposure evaluation, and upgrade/downgrade + history integrity. Both fire where both concerns exist; neither PASS substitutes for the other.
- Application code around the migration, and the quality of CI configuration as configuration → `code-reviewer` skill.
- A pipeline change that alters the process or deployment model, or adopting an ORM / setting `target_metadata` → `architecture-reviewer` skill (ADR territory).
- Root cause of a red FA-02 drill, once this skill has established it is a genuine downgrade defect → `bug-investigator` skill.
