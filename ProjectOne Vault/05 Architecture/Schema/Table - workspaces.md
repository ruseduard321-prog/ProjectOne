---
title: "Table - workspaces"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [database, schema, multi-tenancy]
table_name: "workspaces"
---

# Table — workspaces

Created by migration `8a6f39b07c12` ([[STEP-08 Users and Workspaces Schema]]).

## Purpose

**The tenant boundary.** A workspace is the unit of isolation for data, AI memory, billing and permissions alike ([[CLAUDE|CLAUDE.md]] §16). Every tenant-scoped table added from here on carries a `workspace_id` and filters on it under Row Level Security.

A user's access to one workspace never implies access to another, even for the same user across several workspaces.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. The tenant identifier every other table references. |
| `name` | `text` | NOT NULL, 1–120 chars after trimming | Human-readable workspace name. |
| `owner_id` | `uuid` | NOT NULL, FK → `users.id` `ON DELETE RESTRICT` | The owning user. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Row creation. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Last modification, maintained by `trg_workspaces_touch_row`. |
| `deleted_at` | `timestamptz` | NULL allowed | Soft-deletion marker. |
| `version` | `integer` | NOT NULL, default `1`, `>= 1` | Optimistic-concurrency counter, trigger-maintained. |

See [[Table Conventions]] for the standard column set and trigger behaviour.

### Constraints

| Name | Rule | Why |
|---|---|---|
| `ck_workspaces_name_length` | `length(btrim(name)) BETWEEN 1 AND 120` | Rejects `"   "`, which would render as a nameless workspace in every list. Trimming inside the check means whitespace cannot be used to bypass the minimum. |
| `fk_workspaces_owner_id_users` | FK → `users.id`, `ON DELETE RESTRICT` | See below. |
| `ck_workspaces_version_positive` | `version >= 1` | The counter only ever moves forward. |

### Why `RESTRICT` and not `CASCADE`

Deleting a user must **not** silently destroy the workspaces they own — those workspaces contain other members' work. `RESTRICT` converts what would be a catastrophic data-loss accident into an error message, forcing ownership transfer to be a deliberate action.

This is the deliberate opposite of the `CASCADE` used on [[Table - workspace_members]], where the dependent row genuinely is meaningless without its parent.

## Relationships

| Direction | Table | Behaviour |
|---|---|---|
| References | [[Table - users]] `.id` via `owner_id` | `ON DELETE RESTRICT` |
| Referenced by | [[Table - workspace_members]] `.workspace_id` | `ON DELETE CASCADE` |

**Ownership and membership are separate concepts.** `owner_id` records who owns the workspace; [[Table - workspace_members]] records who can access it. An owner is expected to also hold an `owner`-role membership row, but that invariant is application logic and is not enforced by the schema — enforcing it in the database would require a circular dependency between the two tables' creation order.

## Indexes

| Name | Columns | Type | Why |
|---|---|---|---|
| `workspaces_pkey` | `id` | Unique (PK) | Primary key. |
| `ix_workspaces_owner_id` | `owner_id` WHERE `deleted_at IS NULL` | Partial | Serves "list the workspaces this user owns" — the dashboard's first query. Not speculative: without it, every `users` delete scans this table to enforce `RESTRICT`. |

No unique constraint on `name`. Two different people may reasonably both have a workspace called "Personal", and a global uniqueness rule would be a confusing failure for the second one.

## Row Level Security

> [!warning] Not yet enabled
> RLS arrives in [[STEP-09 Row Level Security Policies]]. This is the table the entire isolation model turns on — a flaw in its policy is a cross-tenant data breach, which is why STEP-09 is separated for focused review rather than bundled here.

See [[Chapter 07 - Database Standards]] and [[Authentication and Authorization]].

---

## Navigation

- **Previous:** [[Table - users]]
- **Next:** [[Table - workspace_members]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[Table - users]] · [[Table - workspace_members]] · [[Database Architecture]]
