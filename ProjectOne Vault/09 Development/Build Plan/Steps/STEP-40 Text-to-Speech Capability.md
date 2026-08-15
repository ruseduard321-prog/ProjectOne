---
title: STEP-40 Text-to-Speech Capability
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-40
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-40 — Text-to-Speech Capability

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, inside the cost model each capability needs.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Implement voice generation through the same contract, producing stored audio assets.

## Why This Step Exists Now

[[Video Generation]] requires voice-over as a named output. Audio is priced differently again from text and images, which makes it the second proof that the per-capability cost model is right.

## Dependencies

- [[STEP-38 AI Capability Contract Expansion]]
- [[STEP-28 Asset Upload and Download]]

## Scope

- At least one TTS provider adapter.
- Voice, language and style parameters as the feature specification requires.
- Generated audio stored as assets.
- Per-character or per-second cost metering, whichever the provider bills.

## Out of Scope

- No speech-to-text.
- No audio editing or mixing — [[STEP-60 Audio Track Assembly]].
- No agent, no UI.

## Surfaces Affected

**Backend:** TTS adapters, generation service, storage integration.

## Required Tests and Proofs

- Generated audio lands in storage with correct tenancy and duration metadata.
- Cost metering matches the provider's billing unit, not a token approximation.
- An unsupported voice or language fails honestly.

## Definition of Done

Speech can be generated through the router with voice and language control, stored as an asset, and metered on the provider's real billing unit.

## Risks and Governance Gates

**Critical** — AI architecture and a new spend surface.

## Audit Gaps Closed

[[Video Generation]] voice-over output — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-39 Image Generation Capability]]
- **Next:** [[STEP-41 Embeddings Capability]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
