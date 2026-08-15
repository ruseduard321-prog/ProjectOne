---
title: STEP-27 Storage Provider Abstraction
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-27
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-27 — Storage Provider Abstraction

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Define the storage contract and one adapter behind it, so no caller ever depends on a specific storage vendor.

## Why This Step Exists Now

The audit names file storage as the single largest blocker in the product: video, publishing, asset review and the whole media agent chain sit behind it. The abstraction comes before the first caller for the same reason [[AI Providers]] did — provider independence is far cheaper to establish before anything depends on it.

## Dependencies

- [[STEP-26 Product Design System Foundation]]

## Scope

- A `StorageProvider` interface — put, get, signed URL, delete — carrying no vendor types.
- One adapter implementing it.
- A tenant-scoped path convention under which a workspace cannot construct a path into another workspace's namespace.
- Configuration and secret handling per [[Environment and Secrets]].

## Out of Scope

- No upload endpoint, no UI and no quota accounting — [[STEP-28 Asset Upload and Download]] and [[STEP-33 Storage Quotas and Lifecycle]].
- No image or video processing of any kind.
- No migration — `assets.storage_path` already exists and is waiting for a backend.

## Surfaces Affected

**Backend:** `app/storage/`. **Infrastructure:** bucket provisioning and credentials. **Database / frontend:** none.

## Required Tests and Proofs

- Path construction is proven tenant-scoped, including against a hostile workspace identifier.
- A signed URL expires, proven by using an expired one rather than by reading the expiry.
- No vendor type appears above the adapter boundary, asserted the way `test_no_ai_call_path_bypasses_governance` already does for the AI layer.

## Definition of Done

A storage provider is reachable through a vendor-neutral interface, tenant-scoped by construction, with credentials handled per [[Environment and Secrets]] and isolation proven by test.

## Risks and Governance Gates

**Critical** — infrastructure configuration and a new tenant boundary ([[CLAUDE|CLAUDE.md]] §21). A path convention wrong here becomes a cross-tenant leak in every later media step, which is why it is settled before there are callers.

## Audit Gaps Closed

**File storage backend** — *Missing, P0, no step* — the audit's largest single blocker

---

## Navigation

- **Previous:** [[STEP-26 Product Design System Foundation]]
- **Next:** [[STEP-28 Asset Upload and Download]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
