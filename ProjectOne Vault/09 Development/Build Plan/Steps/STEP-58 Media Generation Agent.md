---
title: STEP-58 Media Generation Agent
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-58
step_status: Not Started
detail_level: outline
phase: "Media Production"
---

# STEP-58 — Media Generation Agent

**Status:** Not Started
**Phase:** Media Production — Image, audio and voice generation as governed, resumable, storage-backed workflows.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Build the Media Generation Agent, producing visuals from an approved script.

## Why This Step Exists Now

[[Agent Architecture]] places Media Generation after Script. With image capability, storage, parallelism and the invocation cap all in place, this is the first step where the product generates something a creator can look at.

## Dependencies

- [[STEP-57 Script Review and Editing UI]]
- [[STEP-39 Image Generation Capability]]
- [[STEP-53 Workflow Parallel Execution]]

## Scope

- A Media Generation Agent mapping script segments to image generation requests.
- Parallel generation across segments, inside one shared run budget.
- Generated media stored as project assets, linked to their segment.
- A measurable success criterion and per-segment failure handling.

## Out of Scope

- No video assembly.
- No audio.
- No regeneration UI — [[STEP-63 Regeneration and Review UI]].

## Surfaces Affected

**Backend:** agent implementation, parallel step definition, storage integration.

## Required Tests and Proofs

- Parallel generation stays inside one run budget, not one per segment.
- A failed segment does not fail the whole run silently — behaviour is explicit.
- Generated assets are correctly linked and tenant-scoped.
- The invocation cap holds under fan-out.

## Definition of Done

An approved script yields per-segment visuals generated in parallel, stored as linked assets, inside a single shared budget with explicit partial-failure behaviour.

## Risks and Governance Gates

**Critical** — agent architecture and the largest spend surface yet: parallel image generation multiplies cost per run. The shared budget is the control.

## Audit Gaps Closed

**Media Generation Agent** — *Missing, P1, no step*; [[Video Generation]] visuals

---

## Navigation

- **Previous:** [[STEP-57 Script Review and Editing UI]]
- **Next:** [[STEP-59 Voice and Audio Generation]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
