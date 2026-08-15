---
title: STEP-65 Video Export and Delivery
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-65
step_status: Not Started
detail_level: outline
phase: "Video Production"
---

# STEP-65 — Video Export and Delivery

**Status:** Not Started
**Phase:** Video Production — Assembly, rendering, quality checks, regeneration and export.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Produce a final export a user can download or hand to publishing.

## Why This Step Exists Now

[[Video Generation]]'s workflow ends at Final Export. Until a user can get the file out, the pipeline produces artefacts rather than a deliverable.

## Dependencies

- [[STEP-64 Subtitles and Publishing Metadata]]

## Scope

- Export in the formats the product commits to.
- Download through signed URLs.
- Export as a bounded async job.
- Export state visible in the project.

## Out of Scope

- No platform-specific encoding profiles — publishing owns those.
- No DRM or watermarking.

## Surfaces Affected

**Backend:** export job handlers, storage. **Frontend:** export and download surface.

## Required Tests and Proofs

- An exported file is valid and playable.
- Download is signed, expiring and tenant-scoped.
- Export runs asynchronously with a wall-clock ceiling.
- A failed export reports honestly and leaves sources intact.

## Definition of Done

A completed video exports to a downloadable file through a signed, expiring URL, produced asynchronously with bounded runtime.

## Risks and Governance Gates

Bandwidth and storage cost become real here. Signed-URL expiry is the tenant control on distribution.

## Audit Gaps Closed

[[Video Generation]] final export — completes the domain

---

## Navigation

- **Previous:** [[STEP-64 Subtitles and Publishing Metadata]]
- **Next:** [[STEP-66 Channels Domain]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
