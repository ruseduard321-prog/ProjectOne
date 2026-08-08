---
title: Table - projects
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-08
tags: [database, schema, multi-tenancy, projects]
aliases: ["projects", "Projects Table"]
---

# Table — `projects`

**A content project and where it sits in its lifecycle.** Created by migration `e5a91c34d7f2` ([[STEP-20 Projects Schema and Lifecycle]]).

The first *content* table in the schema. Everything before it was platform machinery — identity, tenancy, authorization, AI governance. A project is the first row a user creates because they came here to make something, which is what [[Projects]] describes.

## Columns

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | Maintained by `touch_row()` |
| `deleted_at` | `timestamptz` | Soft deletion |
| `version` | `integer` | Maintained by `touch_row()` |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT` |
| `name` | `text` NOT NULL | CHECK: not blank, `char_length <= 200` |
| `description` | `text` | Nullable; CHECK `char_length <= 2000` |
| `status` | `text` NOT NULL | Default `'idea'`; CHECK against the nine lifecycle states |
| `created_by` | `uuid` NOT NULL | **Not** an FK — same reasoning as `audit_log.actor_id` |

Follows [[Table Conventions]] in full.

One extra constraint exists that is not about this table's own integrity: `uq_projects_id_workspace_id UNIQUE (id, workspace_id)`. `id` is already unique, so it constrains nothing — it exists solely to give [[Table - assets]]'s composite foreign key something to reference.

### `status` is `text` with a CHECK, not an ENUM

Per [[Table Conventions#Enumerated Values]]: adding or renaming a state is one `ALTER` rather than a type rewrite that locks the table. The vocabulary matches `ProjectStatus` in `apps/api/app/services/project_service.py` exactly, and `test_status_vocabulary_matches_the_database` asserts that by inserting every value rather than trusting the two lists were edited together.

### The constraint fixes the vocabulary; the service owns the transitions

**Which transitions are legal is deliberately not in the database.** A CHECK constraint sees one row at a time and cannot compare a new status against the old one; expressing a transition rule here would mean a trigger comparing `OLD` to `NEW` — a second copy of a rule the service already owns, in a language where it is far harder to read and test.

`ProjectService` owns the state machine so it holds for any caller, including the non-HTTP ones later phases bring ([[Workflow Engine]] advances a project without a request in sight). See [[Project Lifecycle]].

The split is the same one `workspace_members.role` uses: the constraint fixes the vocabulary, and application code gives it meaning.

## Row Level Security

Enabled **and** forced. Three policies, `TO authenticated`, following [[RLS Policy Pattern]]:

| Command | Rule |
|---|---|
| SELECT | Live membership of the workspace |
| INSERT | Live membership of the workspace |
| UPDATE | Live membership, `USING` and `WITH CHECK` both |

No DELETE policy and no DELETE grant, deliberately — removal is a soft delete, and a DELETE path would be a second, unaudited one bypassing it.

### Any member may create and edit a project

Not owner/admin, unlike [[Table - provider_credentials]]. A workspace exists so its members can make things, and a content platform where only administrators may create content is not the product [[Projects]] describes. The distinction is **consequence**: a provider key authorizes spend on the customer's upstream account, while a project is the work itself.

### The SELECT policy does not filter `deleted_at`

Required, not stylistic. A SELECT policy filtering `deleted_at IS NULL` makes soft-deleting the table impossible: the `UPDATE` that sets `deleted_at` produces a row the policy no longer matches, and PostgreSQL refuses it with an error naming row-level security while pointing at the UPDATE policy, where nothing is wrong.

This defect cost [[STEP-11a Membership Removal Policy]] and [[STEP-19 Settings and BYOK UI]] a step each. Liveness is filtered in every query instead — see [[RLS Policy Pattern#Liveness belongs in the query, not the policy]].

## Indexes

| Index | Purpose |
|---|---|
| `ix_projects_workspace_id` | The workspace listing; partial on `deleted_at IS NULL` |
| `ix_projects_workspace_id_status` | Filtering a workspace's projects by lifecycle state |

**Project names are deliberately not unique.** Two drafts of the same idea is a normal thing to want, and a uniqueness error on a name is a confusing way to discover the platform disagreed.

## Export and Erasure

Registered as `ProjectStore` in `REGISTERED_STORES` ([[CLAUDE|CLAUDE.md]] §16), in the same change that created the table rather than afterwards — both preceding content tables were registered late and the gap was a silent obligation failure each time.

---

## Navigation

- **Previous:** [[Table - ai_shutdown_switches]]
- **Next:** [[Table - assets]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table - assets]] · [[Project Lifecycle]] · [[Table Conventions]] · [[RLS Policy Pattern]] · [[Schema Overview]] · [[Projects]]
