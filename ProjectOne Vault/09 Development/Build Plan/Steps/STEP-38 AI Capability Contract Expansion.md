---
title: STEP-38 AI Capability Contract Expansion
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-38
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-38 — AI Capability Contract Expansion

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, inside the cost model each capability needs.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Widen the provider contract beyond chat completion, and give each capability the cost model it actually needs.

## Why This Step Exists Now

`Capability.CHAT_COMPLETION` is the only member of the enum, and `cost_per_1k_tokens` is a single scalar per provider. Image pricing is per-image, audio is per-character or per-second — the existing cost model cannot express them, and 15a metering would be wrong the moment a media call is made.

## Dependencies

- [[STEP-31 Workflow Async Execution]]

## Scope

- New `Capability` members for the media and tool operations this roadmap needs.
- Per-capability cost modelling replacing the single scalar, so [[AI Cost Governance]] can meter each honestly.
- Selection, health, retry and fallback extended to capability-aware routing.
- No behaviour change for chat completion.

## Out of Scope

- No provider adapter implements a new capability yet — [[STEP-39 Image Generation Capability]] onward.
- No agent uses any new capability yet.

## Surfaces Affected

**Backend:** `app/ai/provider.py`, `router.py`, `pricing.py`, `governance.py`. **Database:** possible spend-record shape change, expand/contract.

## Required Tests and Proofs

- Existing chat behaviour is unchanged, proven by the existing suite staying green without modification.
- A capability with no provider fails honestly rather than falling back to a provider that cannot serve it.
- Per-capability cost is metered correctly, including a non-token-priced capability.
- Ceilings still bound every capability.

## Definition of Done

The provider contract expresses more than chat completion, each capability meters its real cost through [[AI Cost Governance]], and existing chat behaviour is provably unchanged.

## Risks and Governance Gates

**Critical** — AI architecture and the cost-governance model that protects against unbounded spend. Getting the cost model wrong here silently under-meters every media call built on top of it.

## Audit Gaps Closed

**Image / media generation capability**, **Embeddings capability**, **Tool calling** — all *Missing, P0, no step*; Model selection by capability/latency/cost — *Foundation / Partial*

---

## Navigation

- **Previous:** [[STEP-37 Notification Preferences]]
- **Next:** [[STEP-39 Image Generation Capability]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
