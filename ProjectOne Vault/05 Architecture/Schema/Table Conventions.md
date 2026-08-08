---
title: Table Conventions
category: Architecture/Schema
status: stable
version: "1.3"
last_updated: 2026-08-08
tags: [database, architecture, standards]
aliases: ["Column Conventions", "Standard Columns"]
---

# Table Conventions

The column set, naming rules and constraint patterns **every ProjectOne table follows**. Established by [[STEP-08 Users and Workspaces Schema]] and binding from that point on.

This exists so a new table is written by copying a reviewed pattern rather than re-deciding it. A convention re-derived per table diverges by the fourth table, and reconciling twelve tables later is far more expensive than agreeing once ([[CLAUDE|CLAUDE.md]] §39).

## The Standard Column Set

Every table carries these five columns.

| Column | Type | Default | Nullable | Purpose |
|---|---|---|---|---|
| `id` | `uuid` | `gen_random_uuid()` | No | Primary key |
| `created_at` | `timestamptz` | `now()` | No | Row creation |
| `updated_at` | `timestamptz` | `now()` | No | Last modification, trigger-maintained |
| `deleted_at` | `timestamptz` | — | **Yes** | Soft-deletion marker |
| `version` | `integer` | `1` | No | Optimistic-concurrency counter, trigger-maintained |

### Why each one

- **`uuid` over `bigserial`.** Identifiers can be generated without a database round trip, and they never leak row counts or creation order — a sequential integer in a URL tells anyone how many customers exist. `gen_random_uuid()` is built into PostgreSQL 13+, so this introduces no extension dependency.
- **`timestamptz`, never `timestamp`.** A timestamp without a zone is ambiguous the moment two regions write to it, and the ambiguity is silent — it produces wrong answers, not errors.
- **`deleted_at` rather than `is_deleted`.** A nullable timestamp records *when*, which a boolean cannot, and the boolean is derivable from it (`deleted_at IS NOT NULL`). Soft deletion is a [[CLAUDE|CLAUDE.md]] §13 architectural default, not a per-table choice.
- **`version` for optimistic concurrency.** It exists so a read-modify-write endpoint can detect a lost update rather than silently overwriting one. Nothing consumes it yet; it is far cheaper to add now than to backfill across every table later.

## The `touch_row` Trigger

`updated_at` and `version` are maintained by a database trigger, not by application code:

```sql
CREATE OR REPLACE FUNCTION touch_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$;
```

Attached to each table as:

```sql
CREATE TRIGGER trg_<table>_touch_row
BEFORE UPDATE ON <table>
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION touch_row();
```

**In the database, not the application**, because every write path — the API, a migration, a psql session, a future background job — then gets identical behaviour from one implementation. Application-maintained timestamps are correct until the first code path forgets, and that path is always found in production.

> [!warning] `clock_timestamp()`, not `now()`
> `now()` returns **transaction start time**. A row inserted and then updated inside a single transaction would keep an `updated_at` identical to its `created_at` — the column silently stops meaning anything while still looking populated. `clock_timestamp()` reads the wall clock at statement execution.
>
> This was a real defect caught during STEP-08 validation, not a hypothetical. Any new trigger touching a modification timestamp uses `clock_timestamp()`.
>
> `created_at` keeps `now()` deliberately: rows written by one transaction *should* share a creation instant.

The `WHEN (OLD.* IS DISTINCT FROM NEW.*)` clause suppresses no-op updates, so `UPDATE ... SET x = x` does not inflate the version counter or falsify `updated_at`.

## Naming

| Object | Pattern | Example |
|---|---|---|
| Table | plural, `snake_case` | `workspace_members` |
| Column | singular, `snake_case` | `owner_id` |
| Primary key | `<table>_pkey` (PostgreSQL default) | `users_pkey` |
| Foreign key | `fk_<table>_<column>_<referenced table>` | `fk_workspaces_owner_id_users` |
| Check constraint | `ck_<table>_<rule>` | `ck_users_email_lowercase` |
| Unique index | `uq_<table>_<columns or purpose>` | `uq_users_email_active` |
| Plain index | `ix_<table>_<columns>` | `ix_workspace_members_user_id` |
| Trigger | `trg_<table>_<action>` | `trg_users_touch_row` |

Constraint names are given explicitly rather than left to the database. A generated name is unpredictable across environments, and an error message naming `ck_users_email_lowercase` is diagnosable where `users_check1` is not.

## Soft Deletion and Partial Indexes

**A uniqueness rule on a soft-deletable table is almost always partial.** A plain `UNIQUE` on `users.email` makes deletion permanently reserve the address — the user cannot re-register, and nothing in the error explains why:

```sql
CREATE UNIQUE INDEX uq_users_email_active ON users (email)
WHERE deleted_at IS NULL;
```

The same reasoning applies to lookup indexes: a query filtering `WHERE deleted_at IS NULL` is served better by an index that excludes dead rows entirely.

## Foreign Key Delete Behaviour

The choice is deliberate per relationship, never copied by habit:

| Behaviour | When | Example |
|---|---|---|
| `RESTRICT` | The referenced row's deletion must not silently destroy dependent data | `workspaces.owner_id` — deleting a user must not destroy workspaces containing other people's work |
| `CASCADE` | The dependent row is meaningless without its parent | `workspace_members.workspace_id` — a membership in a deleted workspace means nothing |

`RESTRICT` is the safer default when in doubt: it converts a data-loss accident into an error message.

### A `RESTRICT` foreign key to `workspaces` is also a test-teardown obligation

The protection has a cost that must be paid in the same change, and forgetting it breaks CI in a way that points at the wrong place.

The shared fixture in `apps/api/tests/conftest.py` seeds a workspace for most database-backed tests and deletes it during teardown. Because every dependant listed above is `RESTRICT`, PostgreSQL refuses that delete while any dependent row survives — so **every new table taking a foreign key to `workspaces` must be added to `_WORKSPACE_DEPENDANTS` in the same change that creates it.**

This has already been missed twice. [[STEP-17 AI Router and Provider Abstraction]] added `provider_credentials` and [[STEP-18 AI Cost Governance Controls]] added three more tables, none registered; CI failed with `ForeignKeyViolation: fk_ai_spend_records_workspace_id_workspaces`. [[STEP-20 Projects Schema and Lifecycle]] registered `projects` and `assets` in the same change that created them, which is the intended shape.

One ordering constraint applies to `assets` and is worth stating, since the list's comment otherwise says order is unconstrained: `assets` references `projects` as well as `workspaces`, so it must be cleared before `projects`. Alphabetical order happens to satisfy that — luck rather than design, so a future alphabetical insertion should not be assumed safe on that basis. The failure surfaces **in teardown**, so it appears in whichever database test happened to run last rather than in anything related to the new table — which is a slow way to find a one-line omission.

`tests/test_teardown_completeness.py` now closes it: it queries the catalog for every table referencing `workspaces` and asserts the teardown list matches exactly, in both directions. A new unregistered table fails *there*, naming the table and the fix, instead of failing somewhere unrelated. A second test asserts those foreign keys are still `RESTRICT`, so the production guarantee cannot be quietly downgraded to `CASCADE` to make the error go away.

One detail worth carrying: `ai_shutdown_switches.workspace_id` is **nullable** — a platform-wide kill switch belongs to no workspace. Teardown therefore deletes from these tables unqualified rather than filtering by `workspace_id`, which would leave platform-wide rows behind to leak into the next test.

## Enumerated Values

Use `text` with a `CHECK` constraint, **not** a PostgreSQL `ENUM` type. Adding a value to an enum is easy, but removing or renaming one requires rewriting the type — a locking operation on a live table. A `CHECK` constraint is altered in a single statement.

```sql
role text NOT NULL DEFAULT 'member'
CONSTRAINT ck_workspace_members_role_valid CHECK (role IN ('owner', 'admin', 'member'))
```

## Row Level Security

**Every tenant-scoped table ships its RLS policy in the same migration that creates it** ([[CLAUDE|CLAUDE.md]] §16). A table without RLS is an incomplete migration, not a follow-up task.

The policies themselves follow one reviewed pattern — **[[RLS Policy Pattern]]** — rather than being improvised per table. Read it before adding any tenant-scoped table; it covers the membership helper, the `USING`/`WITH CHECK` split, why `FORCE` is required alongside `ENABLE`, and the isolation test a new table must come with.

[[STEP-08 Users and Workspaces Schema]] is the one deliberate exception in the project's history: the foundational tables were created without RLS because policy work was separated into [[STEP-09 Row Level Security Policies]] for its own focused review. They held no data and no application code touched them in between. That gap is now closed — all three tables have RLS enabled and forced. **The exception does not generalize.**

## Migration Discipline

- Every schema change is a version-controlled migration file. Manual SQL against a live database is forbidden ([[CLAUDE|CLAUDE.md]] §13).
- **History is append-only.** Correcting an applied migration means writing a new one, not editing the old file — the file must keep describing what actually ran.
- **Write `downgrade()` at the same time as `upgrade()`**, and verify it. An untested rollback path is discovered during an incident.
- Expand/contract for anything touching a populated table: add, backfill, cut over, drop — four deploys, never one.

### Migrations run in-process under pytest, so `env.py` must not reconfigure logging

`migrations/env.py` calls `logging.config.fileConfig(...)`, and its `disable_existing_loggers` parameter **must stay `False`**. The default is `True`, which sets `.disabled = True` on every logger not named in `alembic.ini` — that is, every `app.*` logger.

For a standalone `alembic upgrade` that is harmless: the process exits with the migration. Under pytest it is not. The session-scoped `migrated_database` fixture runs migrations **in-process**, so with the default every application logger is silenced from the first database test onward, for the remainder of the run. Any test asserting on log output then fails with an empty capture and no indication why.

This is exactly how it was found: two request-logging assertions passed locally and failed only in CI, because locally the database tests skip and `fileConfig` never runs. The diagnostic signature is a `console` handler on the root logger (Alembic's, from `alembic.ini`) alongside an empty `caplog` while every level and propagation flag looks correct — **loggers being disabled, not filtered.**

The same caution applies to `configure_logging()` in `app/core/logging.py`, which removes its own named handler rather than clearing the root logger's handlers wholesale — clearing them all also destroys `caplog`'s capture handler.

---

## Navigation

- **Previous:** —
- **Next:** [[RLS Policy Pattern]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[RLS Policy Pattern]] · [[Schema Overview]] · [[Table - users]] · [[Table - workspaces]] · [[Table - workspace_members]] · [[Chapter 07 - Database Standards]] · [[Database Architecture]]
