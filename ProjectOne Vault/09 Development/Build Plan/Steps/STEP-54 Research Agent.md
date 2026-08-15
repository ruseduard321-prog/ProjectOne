---
title: STEP-54 Research Agent
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, agents]
step_id: STEP-54
step_status: Not Started
detail_level: outline
phase: "Content Intelligence"
---

# STEP-54 — Research Agent

**Status:** Not Started
**Phase:** Content Intelligence — The first real agent chain: research and script, producing content worth generating media for.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Build the Research Agent, the second agent in [[Agent Architecture]]'s chain.

## Why This Step Exists Now

[[Agent Architecture]] places Research between Planning and Script. A script written without research is a script written from the model's priors alone, which is exactly the confident-unfounded output [[CLAUDE|CLAUDE.md]] 15 warns against.

## Dependencies

- [[STEP-53 Multi-Agent Orchestration]]
- [[STEP-40 Tool Calling Capability]]

## Scope

- A Research Agent with a single responsibility, defined inputs and outputs and a measurable success criterion.
- Tool access for gathering information, inside the tool approval model.
- Findings persisted as structured output the Script Agent can consume.
- Source attribution, so a claim can be traced.

## Out of Scope

- No autonomous browsing without governance.
- No script generation.

## Surfaces Affected

**Backend:** `app/workflows/agents.py` or a package split if the file has outgrown one module.

## Required Tests and Proofs

- The success criterion is enforced, as `PlanningAgent`'s minimum-length check is.
- Cost is metered and bounded per run.
- Tool use respects the approval model.
- Output is consumable by a downstream step, proven by one.

## Definition of Done

A Research Agent produces attributed, structured findings within its budget, gated by the approval model, consumable downstream.

## Risks and Governance Gates

**Critical** — agent architecture and a new spend surface. If it browses externally, source trust and injection resistance are real concerns: retrieved content is data, never instruction.

## Audit Gaps Closed

**Research Agent** — *Missing, P2, no step*

---

## Navigation

- **Previous:** [[STEP-53 Multi-Agent Orchestration]]
- **Next:** [[STEP-55 Script Agent]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
