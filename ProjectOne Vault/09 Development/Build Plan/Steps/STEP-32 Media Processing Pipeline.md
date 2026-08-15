---
title: STEP-32 Media Processing Pipeline
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, backend, infrastructure]
step_id: STEP-32
step_status: Not Started
detail_level: outline
phase: "Platform Substrate"
---

# STEP-32 — Media Processing Pipeline

**Status:** Not Started
**Phase:** Platform Substrate — The absent infrastructure every media, approval and automation capability sits behind: storage, async execution, notifications.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Derive what the product needs from an uploaded file — dimensions, duration, thumbnails, normalised formats — without blocking the request that uploaded it.

## Why This Step Exists Now

Media generation and video assembly both consume derived metadata rather than raw bytes. Establishing derivation once prevents each media step inventing its own.

## Dependencies

- [[STEP-28 Asset Upload and Download]]
- [[STEP-30 Async Job Infrastructure]]

## Scope

- Metadata extraction — dimensions, duration, format, size.
- Thumbnail and preview derivation for supported kinds.
- Derivation executed as an async job, never inline in the upload request.
- Failure handling: a file whose derivation fails is still a stored, retrievable asset.

## Out of Scope

- No transcoding for delivery, no adaptive bitrate — those belong with video export.
- No AI-based analysis of content.

## Surfaces Affected

**Backend:** processing service and job handlers. **Database:** derived-metadata columns or a companion table with RLS. **Infrastructure:** processing dependencies.

## Required Tests and Proofs

- A corrupt file fails derivation without losing the stored asset.
- Derivation runs off the request path, proven by response timing and job state.
- Derived metadata is tenant-scoped like its parent asset.

## Definition of Done

An uploaded file yields derived metadata and a preview where the kind supports it, produced asynchronously, with failures isolated from the asset itself.

## Risks and Governance Gates

**Critical if it adds a table** — schema and RLS. Processing untrusted files is a known attack surface; library choice and sandboxing are decisions to state, not defaults to accept.

## Audit Gaps Closed

Asset preview — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-31 Workflow Async Execution]]
- **Next:** [[STEP-33 Storage Quotas and Lifecycle]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
