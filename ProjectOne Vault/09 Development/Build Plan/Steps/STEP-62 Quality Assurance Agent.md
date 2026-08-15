---
title: STEP-62 Quality Assurance Agent
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, media, backend]
step_id: STEP-62
step_status: Not Started
detail_level: outline
phase: "Video Production"
---

# STEP-62 — Quality Assurance Agent

**Status:** Not Started
**Phase:** Video Production — Assembly, rendering, quality checks, regeneration and export.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Add an AI quality check over generated output, distinct from the deterministic checks that already exist.

## Why This Step Exists Now

[[Agent Architecture]] specifies a QA Agent. The audit is explicit that `QualityCheckStep` is deterministic by design and not a substitute. Once a run produces media, a deterministic length check can no longer tell whether the output is any good.

## Dependencies

- [[STEP-61 Video Assembly Agent]]

## Scope

- A QA Agent assessing generated output against stated criteria.
- Structured findings identifying which component failed, not a pass/fail verdict alone.
- Existing deterministic checks retained — this adds a layer rather than replacing one.
- Cost bounded, and the chained-invocation cap enforced if QA can request regeneration.

## Out of Scope

- No automatic regeneration — the next step decides that policy.
- No replacement of deterministic checks.

## Surfaces Affected

**Backend:** QA agent implementation.

## Required Tests and Proofs

- QA identifies a deliberately degraded component in a fixture.
- QA cost is bounded per run.
- A QA request for regeneration is capped by the STEP-50 ceiling.
- Deterministic checks still run and still gate.

## Definition of Done

A QA Agent produces structured, component-level findings over generated output, within budget, with any regeneration request bounded by the invocation cap.

## Risks and Governance Gates

**Critical** — this is the specific agent [[CLAUDE|CLAUDE.md]] §15a names when describing runaway risk: a QA agent that can request regeneration can loop. The cap from STEP-50 is what makes it safe.

## Audit Gaps Closed

**Quality Assurance Agent** — *Foundation / Partial, P2*

---

## Navigation

- **Previous:** [[STEP-61 Video Assembly Agent]]
- **Next:** [[STEP-63 Regeneration and Review UI]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
