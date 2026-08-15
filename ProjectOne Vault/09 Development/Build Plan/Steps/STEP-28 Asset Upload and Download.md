---
title: STEP-28 Asset Upload and Download
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-28
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-28 — Asset Upload and Download

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give assets real bytes: an upload path that validates and stores, and a retrieval path that serves them back safely.

## Why This Step Exists Now

`assets.storage_path` is null on every row any route can currently create. Until an upload exists, the asset table records intentions rather than content.

## Dependencies

- [[STEP-27 Storage Provider Abstraction]]

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-27 Storage Provider Abstraction]]:

- **The storage contract is fixed and vendor-neutral.** `StorageProvider` (`app/storage/provider.py`) exposes exactly **put, get, signed URL, delete**. There is no listing operation, so any scope here that assumed one needs a different design rather than a new call.
- **This step supplies the `logical_name`, never a path.** No storage method accepts a key, prefix or bucket — `app/storage/keys.py` constructs every key from a workspace id plus a validated logical name. Upload validation therefore covers *file content and size*; **path safety is already guaranteed upstream and must not be re-implemented here**.
- **Logical names are restricted to `[A-Za-z0-9._-]`.** A user-supplied filename will frequently not satisfy this (spaces, non-ASCII, multiple dots are all common), so this step owns deriving a safe logical name from an uploaded filename — and `assets.name` remains where the human-readable original belongs.
- **Signed-URL expiry is bounded at 7 days** by the backend, and `expires_in` is a required argument with no default — the retrieval path must choose it explicitly.
- **Storage configuration is currently optional** (`PROJECTONE_R2_*`, all-four-or-none). **This is the step that makes it required**, since it introduces the first real caller; until then `build_storage_provider()` raises `StorageNotConfiguredError` at the point of use.
- **Erasure registration is genuinely new work.** STEP-27 added a store but no caller, so nothing was registered with `data_ownership_service.py`. Deleting a workspace's objects is therefore this step's obligation, as the Scope below already states.

## Scope

- Upload endpoint with size, MIME and extension validation.
- Retrieval through signed URLs, never a public bucket path.
- `storage_path` populated on the asset row.
- Orphan handling in both directions: a failed upload leaves neither a row pointing at nothing nor an object with no row.
- Registration with the erasure path in `data_ownership_service.py` — a new store holding user data owes deletion coverage ([[CLAUDE|CLAUDE.md]] 16).

## Out of Scope

- No image transformation, thumbnailing or transcoding — [[STEP-32 Media Processing Pipeline]].
- No quota enforcement — [[STEP-33 Storage Quotas and Lifecycle]].
- No upload UI — [[STEP-29 Asset Management UI]].

## Surfaces Affected

**Backend:** asset routes, service, storage integration, erasure registration. **Database:** none (column exists). **Frontend:** none.

## Required Tests and Proofs

- An upload above the size ceiling is refused, proven by response body.
- A disallowed MIME type is refused, including one whose extension lies about its content.
- A cross-tenant download attempt fails through the route layer, not merely at the policy.
- Deleting a workspace removes its stored objects, not only its rows.

## Definition of Done

A user can upload a file to a project and retrieve it, with validation enforced, isolation proven through the route layer, and erasure covering the new store.

## Risks and Governance Gates

**Critical** — public API contract, tenant data boundary, and a new store subject to 16 deletion obligations. Upload endpoints are also a classic injection surface; validation is the step, not a detail of it.

## Audit Gaps Closed

File upload path — *Missing, P0*; Asset download / preview — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-27 Storage Provider Abstraction]]
- **Next:** [[STEP-29 Asset Management UI]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
