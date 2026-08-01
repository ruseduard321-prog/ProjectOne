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

**Enabled and forced** by migration `860a798d204b` ([[STEP-09 Row Level Security Policies]]). The full pattern is [[RLS Policy Pattern]]; what is specific to this table:

| Policy | Command | Rule |
|---|---|---|
| `workspace_members_select_same_workspace` | SELECT | Same workspace |
| `workspace_members_update_same_workspace` | UPDATE | Same workspace, and the row cannot be moved to another |
| `workspace_members_insert_same_workspace` | INSERT | Same workspace — inviting requires already being in it |

> [!warning] This table's policy cannot query this table
> A policy on `workspace_members` that subqueries `workspace_members` **recurses** — PostgreSQL raises `infinite recursion detected in policy for relation`. Verified against a live database during STEP-09, not assumed.
>
> Every clause above therefore routes through `public.app_current_user_workspaces()`, a locked-down `SECURITY DEFINER` function that reads memberships outside RLS. Inlining it would look like a simplification and would break every authenticated query on this table. `test_membership_policy_does_not_recurse` guards against exactly that.

**The bootstrap case does not pass these policies, deliberately.** A workspace creator's own first membership row has no existing membership to test against, so it cannot be inserted by a client. Workspace creation is a two-statement operation belonging in an audited service path ([[STEP-13 Auth Users Workspaces Endpoints]]), not something assembled row by row from outside. This is the one thing about this policy set likely to surprise whoever writes that endpoint.

Role changes and removal rights are [[STEP-11 Authorization and RBAC]]. No DELETE policy exists; removal is a soft delete ([[RLS Policy Pattern#DELETE is granted to no one]]).

See [[Chapter 07 - Database Standards]] and [[Authentication and Authorization]].

---

## Navigation

- **Previous:** [[Table - workspaces]]
- **Next:** [[Table - audit_log]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[RLS Policy Pattern]] · [[Table - users]] · [[Table - workspaces]] · [[Table - audit_log]] · [[Database Architecture]]
