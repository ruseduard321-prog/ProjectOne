---
title: Table - provider_credentials
category: Architecture/Schema
status: stable
version: "1.0"
last_updated: 2026-08-03
tags: [database, schema, ai, security, multi-tenancy]
aliases: ["provider_credentials", "BYOK Table"]
---

# Table — `provider_credentials`

**A workspace's own AI provider API keys**, stored encrypted. Created by migration `f1a4c8d29b57` ([[STEP-17 AI Router and Provider Abstraction]]).

> [!danger] The most sensitive tenant data in the system so far
> A row here authorizes **spend on an account ProjectOne does not own**. A leak is a direct financial loss for the customer, not an inconvenience — which is why this table carries two independent controls (RLS *and* encryption) rather than one.

## Columns

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `created_at` | `timestamptz` | |
| `updated_at` | `timestamptz` | Maintained by `touch_row()` |
| `deleted_at` | `timestamptz` | Soft deletion — revocation sets this |
| `version` | `integer` | Maintained by `touch_row()` |
| `workspace_id` | `uuid` NOT NULL | FK → `workspaces(id)` `ON DELETE RESTRICT` |
| `provider` | `text` NOT NULL | CHECK: `openai`, `anthropic` |
| `encrypted_key` | `text` NOT NULL | AES-256-GCM ciphertext, base64 |
| `last_four` | `text` NOT NULL | CHECK `char_length <= 4` |
| `created_by` | `uuid` NOT NULL | **Not** an FK — see below |

Follows [[Table Conventions]] in full, unlike [[Table - audit_log]] which departs from it deliberately.

### `provider` is `text` with a CHECK, not an ENUM

Adding a provider is one `ALTER` statement rather than a type rewrite that locks the table. **The vocabulary matches `PROVIDER_NAME` in each adapter exactly** — a value here that no adapter answers to is a key that can never be used, so the constraint makes that a loud failure at write time.

### `last_four` exists so nothing has to decrypt for display

A settings screen can render `sk-…a1b2` without the API decrypting anything. Four characters is too few to narrow a brute-force search meaningfully, and is the convention users already recognise from payment forms.

### `created_by` is not a foreign key

Same reasoning as `audit_log.actor_id`: `users.id` is `RESTRICT`-referenced elsewhere, so an FK would mean either blocking a user's deletion forever or cascading the record away with them. The record should outlive the account that created it.

`workspace_id` **is** a foreign key, with `RESTRICT`, so a workspace cannot be hard-deleted out from under its credentials.

## Indexes

```sql
CREATE UNIQUE INDEX uq_provider_credentials_workspace_provider_live
    ON public.provider_credentials (workspace_id, provider)
    WHERE deleted_at IS NULL;
```

**Partial, and that is what makes rotation work.** Rotation is soft-delete-then-insert, so the old row must stop colliding the moment it is deleted. Without the `deleted_at IS NULL` predicate, rotating a key twice would fail with a constraint violation that reads as a bug. Guarded by `test_rotation_is_possible_after_a_soft_delete`.

## Row Level Security

Enabled **and forced**. Follows [[RLS Policy Pattern]], with one asymmetry worth stating.

| Command | Policy | Rule |
|---|---|---|
| SELECT | `provider_credentials_select_same_workspace` | Live membership |
| INSERT | `provider_credentials_insert_privileged` | **`owner` or `admin`** |
| UPDATE | `provider_credentials_update_privileged` | **`owner` or `admin`**, `USING` + `WITH CHECK` |
| DELETE | *(none)* | Denied by default — removal is a soft delete |

**Reads are membership-scoped while writes are role-scoped.** The router runs as whoever made the request, so requiring owner/admin to *read* would mean only admins could use AI at all. Writing is different: a provider key authorizes spend, so it belongs with the roles that control billing-adjacent settings — consistent with the role-aware policies [[STEP-11 Authorization and RBAC]] established on `workspaces`.

`WITH CHECK` on UPDATE is not optional here: without it, an admin could move a credential row into a workspace they do not administer.

### Grants

```sql
REVOKE ALL ON public.provider_credentials FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.provider_credentials TO authenticated;
```

Stated explicitly rather than inherited. **No `TRUNCATE`** matters most — it is not subject to RLS at all, so a role holding it could empty this table regardless of every policy above.

## Encryption

The ciphertext in `encrypted_key` is AES-256-GCM, keyed by `PROJECTONE_BYOK_ENCRYPTION_KEY` from the environment — **never in the database, never in source control**. A database backup on its own therefore does not yield usable provider keys.

This is **defence in depth behind RLS, not a substitute for it.** RLS stops one tenant reading another's row; encryption stops a leaked backup, a mis-scoped support query, or a future admin path from yielding a usable credential. Either alone has a failure mode the other covers.

Full detail — nonce discipline, why GCM, where plaintext exists — in [[AI Router Implementation#BYOK Credentials]].

> [!warning] Rotating the encryption key is not yet supported
> Changing `PROJECTONE_BYOK_ENCRYPTION_KEY` makes every row here undecryptable, and each workspace must re-enter its keys. There is no re-encryption path.

## Testing

`apps/api/tests/test_provider_credential_isolation.py` — 18 tests covering cross-tenant read, cross-tenant write, the role requirement, the DELETE denial, the grants, the partial index, and the `touch_row` trigger.

Includes `test_policies_are_what_makes_these_tests_pass`, which disables RLS, observes the breach, and restores it — [[RLS Policy Pattern]] step 8. An isolation test that would pass with RLS off is asserting nothing.

**These have not yet run against a live database.** See [[STEP-17 AI Router and Provider Abstraction#Live verification handed to the owner]].

---

## Navigation

- **Previous:** [[Table - audit_log]]
- **Next:** [[RLS Policy Pattern]]
- **Parent:** [[Schema Overview]]
- **Related Notes:** [[Table Conventions]] · [[RLS Policy Pattern]] · [[AI Router Implementation]] · [[Table - workspaces]]
