---
title: Table - assets
category: Architecture/Schema
status: stable
version: "1.2"
last_updated: 2026-08-16
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

## `kind` is a closed vocabulary, and the API must mirror it exactly

`ck_assets_kind_valid` permits `document`, `image`, `video`, `audio` and nothing else. **The HTTP schema must enumerate the same four values** — `AssetKind` in `app/schemas/project.py` — and so must the frontend's `ASSET_KINDS`.

This is not a stylistic preference. [[STEP-21 Projects UI]] first typed the API's `kind` as bounded free text, on the reasoning that the asset kinds a content business needs were not settled. Driving the routes against a real database found the consequence in one request: the API accepted `kind: "script"`, validation passed, and PostgreSQL refused the INSERT with a `CheckViolation`. That surfaces as a **500** — a client's malformed request reported as a server fault, with a constraint name in the log instead of a usable message.

**A constraint the edge does not know about is a 500 waiting for its first user.** The general rule this instance teaches: wherever the database constrains a value to a set, the outermost schema enumerates that same set, so the refusal happens at the edge as a 422 naming the valid options.

Three copies now exist — the constraint, the API enum, the frontend union — and each is asserted rather than trusted. `test_asset_kind_vocabulary_matches_the_database` reads `pg_constraint` and compares in both directions; `test_every_accepted_asset_kind_is_actually_storable` posts one asset of each kind through the real route, which is the assertion that would have caught the original defect.

Extending the vocabulary is **one migration plus both enums, in one change** — which is exactly why the column is `text` with a CHECK rather than a PostgreSQL `ENUM` ([[Table Conventions#Enumerated Values]]).

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

## `storage_path` holds a logical name, not a path

**Populated since [[STEP-28 Asset Upload and Download]]**, by the upload route and nothing else. The name predates the design it now describes: what is stored is a *logical name*, never a path, a key or a URL. No migration was needed — the value fits the existing `char_length <= 1024` — and renaming the column was not worth an expand/contract cycle for a cosmetic gain.

**What goes in it.** `StorageProvider.put` returns `StoredObject.locator`, which *is* the logical name it was given, and that is what is persisted. Retrieval passes the two columns straight back:

```python
provider.signed_url(asset.workspace_id, asset.storage_path, ttl)
```

**Never parse, split, strip or prefix it**, and never reconstruct `ws/<uuid>/…` from it. The full object key is internal to `app/storage/keys.py` and is deliberately not what this column holds — see [[ADR-004 Object Storage Provider and Tenant-Safe Key Construction]]. A locator is not a capability: isolation comes from the `workspace_id` supplied alongside it, so two workspaces can legitimately store the identical string.

**The value is derived from the asset's own `id`** (`app/storage/logical_names.py`), which is what makes it unique. `put` overwrites an existing key silently and the contract has no listing operation, so uniqueness is *constructed* rather than checked — two uploads of `photo.png` into one workspace must not resolve to one object.

**Null is ordinary, not broken.** Three cases produce it: an asset recorded through the metadata-only route, a placeholder created before its content exists, and a row whose upload failed after the row was created. The last is deliberate — see [[STEP-28 Asset Upload and Download]] Task 5 — and the download route answers 404 for all three rather than signing a URL to nothing.

**Erasure reaches the bytes.** `AssetStore.erase` reads every non-null `storage_path` and deletes each object before soft-deleting the rows, which is why `ExportableStore.erase` takes a `StorageProvider` at all. Row-driven, because there is nothing to enumerate: **these rows are the only index of what exists in storage.** Soft-deleting a row still does not remove bytes on its own ([[CLAUDE|CLAUDE.md]] §16).

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

**Erasure removes the objects too, since [[STEP-28 Asset Upload and Download]].** `AssetStore.erase` receives a `StorageProvider` and deletes each non-null locator before marking the rows. Objects first, rows second: the rows are the only record of which objects exist, so destroying them before the bytes would leave nothing able to say what survived.

---

## Navigation

- **Previous:** [[Table - projects]]
- **Next:** —
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table - projects]] · [[Project Lifecycle]] · [[Table Conventions]] · [[RLS Policy Pattern]] · [[Schema Overview]] · [[Projects]]
