---
title: STEP-28 Asset Upload and Download
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-28
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-28 — Asset Upload and Download

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give assets real bytes: an upload path that validates and stores, and a retrieval path that serves them back safely.

## Why This Step Exists Now

`assets.storage_path` is null on every row any route can currently create. Until an upload exists, the asset table records intentions rather than content.

## Dependencies

- [[STEP-27 Storage Provider Abstraction]]

## Scope

- Upload endpoint with size, MIME and extension validation.
- Retrieval through signed URLs, never a public bucket path.
- `storage_path` populated on the asset row.
- Orphan handling in both directions: a failed upload leaves neither a row pointing at nothing nor an object with no row.
- Registration with the erasure path in `data_ownership_service.py` — a new store holding user data owes deletion coverage ([[CLAUDE|CLAUDE.md]] §16).

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
