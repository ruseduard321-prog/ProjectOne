---
title: STEP-39 Image Generation Capability
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-39
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-39 — Image Generation Capability

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, inside the cost model each capability needs.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Implement image generation end to end through the provider abstraction and into storage.

## Why This Step Exists Now

[[Video Generation]] lists visuals among its required outputs, and the Media Generation Agent cannot exist without this. It is the first proof that the widened capability contract works.

## Dependencies

- [[STEP-38 AI Capability Contract Expansion]]
- [[STEP-28 Asset Upload and Download]]

## Scope

- At least one provider adapter implementing image generation.
- Generated images stored as assets through the storage path, never held in memory or returned inline.
- Per-image cost metering through the existing governance controls.
- Failure and fallback behaviour consistent with the chat path.

## Out of Scope

- No image editing, inpainting or variation.
- No agent — [[STEP-58 Media Generation Agent]].
- No UI.

## Surfaces Affected

**Backend:** provider adapters, generation service, storage integration. **Database:** none beyond assets.

## Required Tests and Proofs

- A generated image lands in storage as an asset with correct tenancy.
- Cost is metered per image and trips a ceiling when exceeded.
- A provider failure falls back or fails honestly, never returning a placeholder as though it were generated.

## Definition of Done

An image can be generated through the router, stored as a tenant-scoped asset, and metered accurately against the workspace's budget.

## Risks and Governance Gates

**Critical** — AI architecture and a new spend surface. Image spend is materially higher per call than text; ceilings are the step, not an afterthought.

## Audit Gaps Closed

Image / media generation capability — *Missing, P0*; [[Video Generation]] visuals output

---

## Navigation

- **Previous:** [[STEP-38 AI Capability Contract Expansion]]
- **Next:** [[STEP-40 Text-to-Speech Capability]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
