---
title: STEP-61 Video Assembly Agent
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-61
step_status: Not Started
detail_level: outline
phase: "Video Production"
---

# STEP-61 — Video Assembly Agent

**Status:** Not Started
**Phase:** Video Production — Assembly, rendering, quality checks, regeneration and export.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Compose visuals, audio and timing into a rendered video.

## Why This Step Exists Now

The headline capability of [[Video Generation]] and the point where every prior phase converges: storage holds the pieces, async execution gives the time to render, parallelism made generation feasible, and the agent chain produced the content.

## Dependencies

- [[STEP-60 Audio Track Assembly]]
- [[STEP-54 Multi-Agent Orchestration]]

## Scope

- A Video Assembly Agent composing visuals and audio against script timing.
- Rendering executed as a long-running async job with progress reporting.
- Rendered output stored as a project asset.
- A measurable success criterion — a video of the expected duration that actually plays.

## Out of Scope

- No subtitles — [[STEP-64 Subtitles and Publishing Metadata]].
- No transitions or effects library beyond what assembly requires.
- No manual timeline editor.

## Surfaces Affected

**Backend:** assembly agent, render job handlers. **Infrastructure:** rendering dependencies and compute sizing.

## Required Tests and Proofs

- A rendered video plays and matches expected duration.
- Rendering runs as a bounded async job with a wall-clock ceiling.
- Progress is observable during a long render.
- A failed render leaves source assets intact and reports honestly.

## Definition of Done

An approved script with generated visuals and audio renders into a playable video stored as an asset, produced asynchronously with observable progress and bounded runtime.

## Risks and Governance Gates

**Critical** — agent architecture and the most compute-intensive path in the product. Render duration and cost ceilings are mandatory; an unbounded render is an unbounded infrastructure bill.

## Audit Gaps Closed

**Video Assembly Agent**, **Video composition / rendering** — *Missing, P1, no step*

---

## Navigation

- **Previous:** [[STEP-60 Audio Track Assembly]]
- **Next:** [[STEP-62 Quality Assurance Agent]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
