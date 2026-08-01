---
title: "Table - users"
category: Database Table
status: stable
version: "1.0"
last_updated: 2026-08-01
tags: [database, schema]
table_name: "users"
---

# Table — users

Created by migration `8a6f39b07c12` ([[STEP-08 Users and Workspaces Schema]]).

## Purpose

The application-side profile for a person using ProjectOne. It holds the attributes ProjectOne owns — display name, and the platform-side record of the account — and is keyed to the identity Supabase Auth owns.

**It is not an identity store.** Passwords, MFA factors, sessions, OAuth links and email confirmation all live in `auth.users`, managed by Supabase Auth. Duplicating any of that here would create two sources of truth for identity, which is precisely how "signed in but no profile" bugs happen.

## Columns

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `uuid` | PK, default `gen_random_uuid()` | Primary key. Holds the same value as `auth.users.id` — see [[#Relationship to Supabase Auth]]. |
| `email` | `text` | NOT NULL, lowercase, length 3–320, unique among live rows | The user's address, denormalized from `auth.users`. |
| `display_name` | `text` | NULL allowed; if present, not blank | Optional human-readable name. |
| `created_at` | `timestamptz` | NOT NULL, default `now()` | Row creation. |
| `updated_at` | `timestamptz` | NOT NULL, default `now()` | Last modification, maintained by `trg_users_touch_row`. |
| `deleted_at` | `timestamptz` | NULL allowed | Soft-deletion marker. |
| `version` | `integer` | NOT NULL, default `1`, `>= 1` | Optimistic-concurrency counter, trigger-maintained. |

See [[Table Conventions]] for why the standard five columns exist and how the trigger behaves.

### Constraints

| Name | Rule | Why |
|---|---|---|
| `ck_users_email_lowercase` | `email = lower(email)` | Prevents `Bob@x.com` and `bob@x.com` becoming two accounts. Rejects rather than silently lowercasing, so the stored value is exactly what was sent. `citext` would be tidier but is an extension; this keeps the schema dependency-free. |
| `ck_users_email_length` | `length(email) BETWEEN 3 AND 320` | 320 is the RFC maximum; 3 is the shortest possible address (`a@b`). |
| `ck_users_display_name_not_blank` | NULL or non-blank after trimming | Distinguishes "no name given" (NULL) from `"   "`, which renders as an invisible user. |
| `ck_users_version_positive` | `version >= 1` | The counter only ever moves forward. |

## Relationships

| Direction | Table | Behaviour |
|---|---|---|
| Referenced by | [[Table - workspaces]] `.owner_id` | `ON DELETE RESTRICT` — a user owning workspaces cannot be deleted |
| Referenced by | [[Table - workspace_members]] `.user_id` | `ON DELETE CASCADE` — memberships die with the user |

### Relationship to Supabase Auth

`users.id` carries the same value as `auth.users.id`, but there is **deliberately no foreign key** to it.

`auth` is owned and migrated by Supabase. A cross-schema foreign key would couple ProjectOne's migration history to a schema this project does not control, and to a role whose grants may change under it. [[STEP-10 Authentication Backend]] owns how the link is established and enforced in practice.

`email` is likewise denormalized from `auth.users` rather than joined, because every "who is in this workspace" listing would otherwise cross into a schema the API's role may not read. STEP-10 owns keeping the copy in step with the authoritative value.

## Indexes

| Name | Columns | Type | Why |
|---|---|---|---|
| `users_pkey` | `id` | Unique (PK) | Primary key. |
| `uq_users_email_active` | `email` WHERE `deleted_at IS NULL` | Partial unique | Two live users must never share an address, but a soft-deleted user must not permanently reserve one. A plain `UNIQUE` would block re-registration forever. |

No index on `deleted_at` alone — nothing queries it in isolation, and speculative indexing is forbidden ([[CLAUDE|CLAUDE.md]] §13).

## Row Level Security

> [!warning] Not yet enabled
> RLS arrives in [[STEP-09 Row Level Security Policies]], immediately after the step that created this table. Until then no application code touches it and it holds no data. See [[Table Conventions#Row Level Security]] — this is a one-time, deliberate exception, not a precedent.

See [[Chapter 07 - Database Standards]] and [[Authentication and Authorization]].

---

## Navigation

- **Previous:** [[Schema Overview]]
- **Next:** [[Table - workspaces]]
- **Parent:** [[Database MOC]]
- **Related Notes:** [[Table Conventions]] · [[Table - workspaces]] · [[Table - workspace_members]] · [[Database Architecture]]
