---
title: STEP-39 Embeddings Capability
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-39
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-39 — Embeddings Capability

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, with every prompt versioned before the agents that depend on them are written.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Implement embedding generation, the retrieval primitive the Memory System needs.

## Why This Step Exists Now

[[Memory System]]'s retrieval flow is relevance-based. Without embeddings, memory retrieval can only be recency-based, which is the bounded window chat already has.

## Dependencies

- [[STEP-36 AI Capability Contract Expansion]]

## Scope

- Embedding capability on the provider contract with at least one adapter.
- Vector storage decision and implementation, including the extension or column type it requires.
- Similarity query support.
- Cost metering per embedding call.

## Out of Scope

- No memory schema — [[STEP-44 Memory Schema and Scopes]].
- No retrieval policy, no RAG pipeline.
- No UI.

## Surfaces Affected

**Backend:** adapters, embedding service. **Database:** vector storage and indexing. **Infrastructure:** database extension if required.

## Required Tests and Proofs

- Similarity search returns sensible ordering on a known fixture set.
- Vectors are tenant-scoped like any other tenant data.
- Cost is metered per call.

## Definition of Done

Text can be embedded and stored, similarity-queried within a tenant boundary, and metered — with the storage choice recorded.

## Risks and Governance Gates

**Critical** — database schema, a possible extension, and a new spend surface. Vector storage choice is an architectural decision that may warrant an ADR.

## Audit Gaps Closed

**Embeddings capability** — *Missing, P0, no step*

---

## Navigation

- **Previous:** [[STEP-38 Text-to-Speech Capability]]
- **Next:** [[STEP-40 Tool Calling Capability]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
