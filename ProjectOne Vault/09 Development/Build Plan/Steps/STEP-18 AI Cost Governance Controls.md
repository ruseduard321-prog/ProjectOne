---
title: STEP-18 AI Cost Governance Controls
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-07-31
tags: [engineering, workflow, build-step, ai,backend,security]
step_id: STEP-18
step_status: Not Started
detail_level: outline
---

# STEP-18 — AI Cost Governance Controls

**Status:** Not Started
**Detail level:** outline — expanded to full detail by [[STEP-17 AI Router and Provider Abstraction]], per [[Execution Protocol]].

## Goal

Every [[CLAUDE|CLAUDE.md]] §15a control, built into the router rather than bolted on: budget ceilings, circuit breakers, retry limits, execution limits, usage monitoring, runaway-agent caps, emergency shutdown.

## Scope

§15a treats these as equivalent to a security requirement — skipping ahead is explicitly forbidden. Controls must be demonstrably **tripping under test**, not merely configured.

## Prerequisites

- [[STEP-17 AI Router and Provider Abstraction]] — `Done`

## Required Documentation

- [[CLAUDE|CLAUDE.md]] §15a
- [[AI Providers]]
- [[Agent Architecture]]

## Tasks

Not yet expanded. [[STEP-17 AI Router and Provider Abstraction]] writes this section, when the surrounding code exists and the tasks can be accurate rather than imagined.

## Validation

Not yet expanded.

## Definition of Done

Not yet expanded.

---

## Navigation

- **Previous:** [[STEP-17 AI Router and Provider Abstraction]]
- **Next:** [[STEP-19 Settings and BYOK UI]]
- **Parent:** [[Build Plan]]
