---
title: STEP-63 Subtitles and Publishing Metadata
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-63
step_status: Not Started
detail_level: outline
phase: "Video Production"
---

# STEP-63 — Subtitles and Publishing Metadata

**Status:** Not Started
**Phase:** Video Production — Assembly, rendering, quality checks, regeneration and export.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Generate the remaining named outputs: subtitles, title, description, hashtags and thumbnail.

## Why This Step Exists Now

[[Video Generation]] lists all of these as required outputs. They are grouped because each is a small generation over content that already exists, and splitting them further would create steps too small to justify their own PRs.

## Dependencies

- [[STEP-62 Regeneration and Review UI]]

## Scope

- Subtitle generation with timing from the audio track.
- Title, description and hashtag generation.
- Thumbnail generation or selection from existing visuals.
- All outputs stored as linked project assets and individually editable.

## Out of Scope

- No platform-specific formatting — that belongs with publishing.
- No translation or localisation.

## Surfaces Affected

**Backend:** generation steps. **Frontend:** editing surfaces for each output.

## Required Tests and Proofs

- Subtitle timing aligns with audio within tolerance.
- Each output is individually regenerable and editable.
- Generation cost is bounded.
- Outputs persist as retrievable assets.

## Definition of Done

Subtitles, title, description, hashtags and thumbnail are generated, editable, and stored as linked assets with correct timing where applicable.

## Risks and Governance Gates

Moderate. Spend is small per output but they are numerous; the run budget still bounds the total.

## Audit Gaps Closed

[[Video Generation]] subtitles, title, description, hashtags, thumbnail — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-62 Regeneration and Review UI]]
- **Next:** [[STEP-64 Video Export and Delivery]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
