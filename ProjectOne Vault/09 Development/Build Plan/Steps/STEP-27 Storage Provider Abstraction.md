---
title: STEP-27 Storage Provider Abstraction
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-27
step_status: Not Started
detail_level: full
phase: "Platform Substrate"
---

# STEP-27 — Storage Provider Abstraction

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, and enough notification to make an asynchronous run visible.
**Detail level:** full — expanded by [[STEP-26 Product Design System Foundation]], per [[Execution Protocol#Progressive Detail]].

## Objective

Define the storage contract and one adapter behind it, so no caller ever depends on a specific storage vendor.

## Why This Step Exists Now

The audit names file storage as the single largest blocker in the product: video, publishing, asset review and the whole media agent chain sit behind it. The abstraction comes before the first caller for the same reason [[AI Providers]] did — provider independence is far cheaper to establish before anything depends on it.

## Dependencies

- [[STEP-26 Product Design System Foundation]] — `Done`

## Inherited from earlier steps

Recorded during synchronization, not expansion.

Added by [[STEP-26 Product Design System Foundation]]:

- **STEP-26 changed nothing this step depends on.** It touched the frontend token layer, the global font wiring and a CI check. This step is backend and infrastructure; the two do not meet. No assumption below was revised because of it.
- **CI gained one step in the `web` job** (`Verify colour contrast (WCAG AA)`), which runs from the repository root using system Python and no Node dependencies. Relevant here only as precedent: a repository-root check can be added to a job whose `defaults.run.working-directory` is an app, by setting `working-directory: .` on that step.

Standing facts this step is built on, verified in the codebase at expansion time:

- **`assets.storage_path` already exists** (`text`, nullable) on the `assets` table created by migration `e5a91c34d7f2`, and is **null on every row any route can create today**. `app/routers/projects.py` says so explicitly: no bytes cross the boundary yet. **No migration is needed by this step.**
- **The AI layer is the pattern to mirror**, and it is a real precedent rather than an analogy: `app/ai/provider.py` defines an ABC that imports no HTTP client, no vendor SDK and no FastAPI, with implementations in `app/ai/providers/`. Its docstring records *why* an ABC rather than a `Protocol` — structural typing would accept a broken provider silently and fail on a real user's request, while an ABC fails at import. **The same reasoning applies here and the same shape should be used.**
- **The AI interface was deliberately kept narrow** — no streaming, no embeddings, no capability no scheduled step consumes. That restraint is the precedent this step follows, not just its file layout.
- **Configuration uses `pydantic-settings` with `SecretStr`** (`app/core/config.py`), which keeps values out of logs, tracebacks and `repr()`. Credentials for storage go through the same mechanism — see [[Environment and Secrets]].
- **RLS enforces the workspace boundary at the database**, not a `WHERE workspace_id = …` in a repository (`app/repositories/projects.py`). **Object storage has no RLS**, which is exactly why the path convention in this step carries the isolation burden that the database carries elsewhere. This is the step's central risk.

## Scope

- A `StorageProvider` interface — put, get, signed URL, delete — carrying no vendor types.
- One adapter implementing it.
- A tenant-scoped path convention under which a workspace cannot construct a path into another workspace's namespace.
- Configuration and secret handling per [[Environment and Secrets]].

## Out of Scope

- No upload endpoint, no UI and no quota accounting — [[STEP-28 Asset Upload and Download]] and [[STEP-33 Storage Quotas and Lifecycle]].
- No image or video processing of any kind.
- No migration — `assets.storage_path` already exists and is waiting for a backend.
- **No second adapter.** Provider independence is proven by the boundary, not by writing two implementations of it before either has a caller.
- **No capability the interface does not need yet** — no multipart upload, no resumable upload, no copy/move, no listing. Adding a method later is cheap; removing a speculative one is a breaking change to every implementation ([[CLAUDE|CLAUDE.md]] §29/§35).

## Tasks

1. **Define the `StorageProvider` contract** in `app/storage/provider.py` as an ABC, mirroring `app/ai/provider.py`'s shape and its restraint. Four operations only: put, get, signed URL, delete. **No vendor type appears in a signature or a return type** — bytes, `str`, and the module's own dataclasses, nothing else.
2. **Define the tenant-scoped path convention** and implement it as the *only* way a path is constructed. A caller supplies a workspace id and a logical name; it never supplies a path. This is the step's security-critical surface — see Risks.
3. **Implement one adapter** in `app/storage/providers/`, behind the interface.
4. **Wire configuration** through `app/core/config.py` using `SecretStr`, following the existing pattern, and add the variables to both `.env.example` templates per [[Environment and Secrets]].
5. **Write the tests named in Required Tests and Proofs**, including the architectural boundary test.
6. **Document** the contract and the path convention, and update [[Environment and Secrets]] and [[Backend Architecture]] where they are affected ([[CLAUDE|CLAUDE.md]] §19).

## Required Tests and Proofs

- Path construction is proven tenant-scoped, including against a hostile workspace identifier. **Traversal, absolute paths, encoded separators and a workspace id chosen to prefix another workspace's namespace are all covered** — the last is the one a naive `f"{workspace_id}/{name}"` fails, because `ws-1` prefixes `ws-10`.
- A signed URL expires, proven by **using an expired one** rather than by reading the expiry off the object.
- No vendor type appears above the adapter boundary, asserted as an executable test in the manner of `test_no_route_can_reach_the_router_without_the_ai_service` in `tests/test_ai_cost_governance.py` — an architectural boundary that a future change cannot quietly cross.
- Deleting an object a workspace does not own fails, and fails **closed**.

## Definition of Done

A storage provider is reachable through a vendor-neutral interface, tenant-scoped by construction, with credentials handled per [[Environment and Secrets]] and isolation proven by test.

## Risks and Governance Gates

**Critical** — infrastructure configuration and a new tenant boundary ([[CLAUDE|CLAUDE.md]] §21). A path convention wrong here becomes a cross-tenant leak in every later media step, which is why it is settled before there are callers.

> [!warning] Object storage has no Row Level Security
> Everywhere else in this product the workspace boundary is enforced by the database ([[CLAUDE|CLAUDE.md]] §16), and a repository that forgot to filter would still be safe. **Object storage has no equivalent.** The path convention *is* the isolation mechanism, and a bug in it is a cross-tenant data leak with no second line of defence.
>
> This is why path construction is the interface's responsibility and never the caller's, and why the hostile-identifier test is a required proof rather than a nice-to-have.

**Owner approval gate** — Critical, so the owner reviews before merge.

## Audit Gaps Closed

**File storage backend** — *Missing, P0, no step* — the audit's largest single blocker

---

## Navigation

- **Previous:** [[STEP-26 Product Design System Foundation]]
- **Next:** [[STEP-28 Asset Upload and Download]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]] · [[Environment and Secrets]] · [[Backend Architecture]]
