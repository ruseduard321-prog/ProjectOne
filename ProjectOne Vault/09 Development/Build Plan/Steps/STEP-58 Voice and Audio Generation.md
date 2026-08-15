---
title: STEP-58 Voice and Audio Generation
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-58
step_status: Not Started
detail_level: outline
phase: "Media Production"
---

# STEP-58 — Voice and Audio Generation

**Status:** Not Started
**Phase:** Media Production — Image, audio and voice generation as governed, resumable, storage-backed workflows.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Generate voice-over from the approved script and store it as timed audio assets.

## Why This Step Exists Now

[[Video Generation]] names voice-over as a required output, and assembly needs audio with known timing to synchronise against.

## Dependencies

- [[STEP-57 Media Generation Agent]]
- [[STEP-38 Text-to-Speech Capability]]

## Scope

- Voice generation per script segment, with voice, language and style from the project's inputs.
- Duration and timing metadata captured per segment.
- Audio stored as linked project assets.
- Cost metered on the provider's real billing unit.

## Out of Scope

- No mixing, no background music, no sound effects — [[STEP-59 Audio Track Assembly]].
- No manual voice editing.

## Surfaces Affected

**Backend:** generation step, storage integration, timing metadata.

## Required Tests and Proofs

- Timing metadata matches the actual audio duration.
- Segment audio is linked to its script segment.
- Cost is metered per billing unit and bounded.
- An unsupported voice fails honestly.

## Definition of Done

Voice-over is generated per segment with accurate timing metadata, stored as linked assets, and metered correctly.

## Risks and Governance Gates

**Critical** — agent/AI architecture and spend. Timing accuracy is load-bearing for assembly; a wrong duration desynchronises the whole video.

## Audit Gaps Closed

[[Video Generation]] voice-over output — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-57 Media Generation Agent]]
- **Next:** [[STEP-59 Audio Track Assembly]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
