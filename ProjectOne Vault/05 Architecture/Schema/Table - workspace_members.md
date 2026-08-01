---
title: "Table - workspace_members"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [database, schema, multi-tenancy]
table_name: "workspace_members"
---

# Table — workspace_members

Created by migration `8a6f39b07c12` ([[STEP-08 Users and Workspaces Schema]]).

## Purpose

Joins users to workspaces and records the role each member holds there. **This is the table Row Level Security will consult** to answer "may this user see this row" ([[STEP-09 Row Level Security Policies]]).

Membership is its own table rather than a `workspace_id` column on [[Table - users]] because the relationship is genuinely many-to-many: a user belongs to several workspaces, a workspace holds several users. Collapsing it into a single column would have to be undone by the first invite feature.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. |
| `workspace_id` | `uuid` | NOT NULL, FK → `workspaces.id` `ON DELETE CASCADE` | The workspace. |
| `user_id` | `uuid` | NOT NULL, FK → `users.id` `ON DELETE CASCADE` | The member. |
| `role` | `text` | NOT NULL, default `'member'`, one of `owner`/`admin`/`member` | The member's role in this workspace. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Row creation — effectively when the user joined. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Last modification, maintained by `trg_workspace_members_touch_row`. |
| `deleted_at` | `timestamptz` | NULL allowed | Soft-deletion marker — effectively when the user was removed. |
| `version` | `integer` | NOT NULL, default `1`, `>= 1` | Optimistic-concurrency counter, trigger-maintained. |

See [[Table Conventions]] for the standard column set and trigger behaviour.

### Constraints

| Name | Rule | Why |
|---|---|---|
| `ck_workspace_members_role_valid` | `role IN ('owner', 'admin', 'member')` | Fixes the vocabulary at the database layer. |
| `fk_workspace_members_workspace_id_workspaces` | FK → `workspaces.id`, `ON DELETE CASCADE` | A membership in a deleted workspace is meaningless. |
| `fk_workspace_members_user_id_users` | FK → `users.id`, `ON DELETE CASCADE` | A membership for a deleted user is meaningless. |
| `ck_workspace_members_version_positive` | `version >= 1` | The counter only ever moves forward. |

### Why `text` + `CHECK` rather than a PostgreSQL `ENUM`

Adding a value to an enum type is easy, but **removing or renaming one requires rewriting the type** — a locking operation against a live table. A `CHECK` constraint is altered in a single statement. Roles are exactly the kind of vocabulary that gets revised as a product matures.

**This fixes the vocabulary, not the permissions.** What each role actually allows is [[STEP-11 Authorization and RBAC]]. Nothing in this schema grants or denies anything yet.

## Relationships

| Direction | Table | Behaviour |
|---|---|---|
| References | [[Table - workspaces]] `.id` | `ON DELETE CASCADE` |
| References | [[Table - users]] `.id` | `ON DELETE CASCADE` |

`CASCADE` on both sides is the deliberate opposite of the `RESTRICT` on [[Table - workspaces]] `.owner_id`. The distinction: a membership row has no meaning without both ends, so removing it alongside either parent is the correct outcome. A workspace, by contrast, holds other people's work and must never disappear as a side effect.

## Indexes

| Name | Columns | Type | Why |
|---|---|---|---|
| `workspace_members_pkey` | `id` | Unique (PK) | Primary key. |
| `uq_workspace_members_active` | `(workspace_id, user_id)` WHERE `deleted_at IS NULL` | Partial unique | One live membership per user per workspace. Partial so that removing someone does not permanently prevent re-inviting them. Its leading column also serves "who is in this workspace". |
| `ix_workspace_members_user_id` | `user_id` WHERE `deleted_at IS NULL` | Partial | Serves "which workspaces does this user belong to" — the query every authenticated request runs once RLS lands. |

The two indexes cover both directions of the join deliberately: the unique index leads on `workspace_id`, so a separate `user_id` index is needed for the reverse lookup rather than being redundant with it.

## Row Level Security

> [!warning] Not yet enabled
> RLS arrives in [[STEP-09 Row Level Security Policies]]. This table is the one the policies on every other tenant table will consult, so its own policy needs particular care — a recursive policy that queries the table it protects is a common and subtle failure.

See [[Chapter 07 - Database Standards]] and [[Authentication and Authorization]].

---

## Navigation

- **Previous:** [[Table - workspaces]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[Table - users]] · [[Table - workspaces]] · [[Database Architecture]]
