---
title: Table - assets
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-08
tags: [database, schema, multi-tenancy, projects]
aliases: ["assets", "Assets Table"]
---

# Table — `assets`

**A file or document belonging to one project.** Created by migration `e5a91c34d7f2` ([[STEP-20 Projects Schema and Lifecycle]]), alongside [[Table - projects]].

## Columns

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | Maintained by `touch_row()` |
| `deleted_at` | `timestamptz` | Soft deletion |
| `version` | `integer` | Maintained by `touch_row()` |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT` |
| `project_id` | `uuid` NOT NULL | Part of the composite FK below |
| `name` | `text` NOT NULL | CHECK: not blank, `char_length <= 200` |
| `kind` | `text` NOT NULL | CHECK: `document`, `image`, `video`, `audio` |
| `storage_path` | `text` | Nullable; CHECK `char_length <= 1024` |
| `created_by` | `uuid` NOT NULL | **Not** an FK |

Follows [[Table Conventions]] in full.

## `workspace_id` is denormalized, and constrained rather than trusted

An asset belongs to one project, and that project belongs to one workspace, so `workspace_id` is derivable by a join. It is stored anyway.

**The reason is the RLS policy.** Deriving it would mean a policy that joins:

```sql
USING (project_id IN (SELECT id FROM projects WHERE workspace_id IN (...)))
```

That is evaluated per row, reads a second table under RLS itself, and makes this table's tenant boundary depend on the correctness of the policy on `projects` rather than on the membership helper directly. Storing one uuid buys a policy identical in shape to every other tenant table's — the property [[RLS Policy Pattern]] exists to preserve.

> [!important] The composite foreign key is what makes the denormalization safe
> `fk_assets_project_id_projects` references `projects (id, workspace_id)`, not `projects (id)`. It forces an asset's workspace to be the workspace its project actually belongs to.
>
> Without it, `workspace_id` would be a client-supplied claim. An INSERT naming the caller's **own** workspace — satisfying the RLS policy, which only tests `workspace_id` — while pointing `project_id` at another tenant's project would be accepted, and that tenant's project would silently accumulate a foreign asset. RLS cannot see the mismatch, so a second mechanism has to.
>
> `test_an_asset_cannot_claim_a_project_from_another_workspace` proves the refusal, and it fails on the foreign key rather than on RLS — which is the point.

## `storage_path` points at nothing yet

No storage backend is chosen ([[STEP-20 Projects Schema and Lifecycle]]'s Scope excludes Generation), so this is an opaque locator rather than a URL with a format the migration would be guessing at. It is nullable because an asset row can legitimately exist before its content does — a placeholder created when generation is queued is the obvious case.

**The step that adds a storage backend owes it a deletion path.** Erasure is end-to-end ([[CLAUDE|CLAUDE.md]] §16); soft-deleting this row does not remove the bytes it points at.

## Row Level Security

Enabled **and** forced. Three policies, `TO authenticated`, identical in shape to [[Table - projects]]: SELECT, INSERT and UPDATE all requiring live membership of the workspace, with `USING` and `WITH CHECK` both present on UPDATE. No DELETE policy, no DELETE grant.

The SELECT policy does not filter `deleted_at` — see [[Table - projects#The SELECT policy does not filter deleted_at]] for why, and note that this table is soft-deleted too, so the rule applies identically.

## Indexes

| Index | Purpose |
|---|---|
| `ix_assets_project_id` | Listing one project's assets; partial on `deleted_at IS NULL` |
| `ix_assets_workspace_id` | Workspace-wide export and erasure |

## Export and Erasure

Registered as `AssetStore` in `REGISTERED_STORES`, separately from `ProjectStore` rather than nested inside its export. The registry's per-store counts are what make an erasure auditable: reporting `"projects": 3` while silently having removed forty assets tells the reader less than two honest numbers do.

The export carries `storage_path` but not the content, which lives outside PostgreSQL.

---

## Navigation

- **Previous:** [[Table - projects]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table - projects]] · [[Project Lifecycle]] · [[Table Conventions]] · [[RLS Policy Pattern]] · [[Schema Overview]] · [[Projects]]
