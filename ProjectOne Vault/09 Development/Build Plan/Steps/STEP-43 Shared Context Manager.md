---
title: STEP-43 Shared Context Manager
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-43
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-43 — Shared Context Manager

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls [[CLAUDE|CLAUDE.md]] §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Extract context assembly into a shared component usable by chat, agents and workflows alike.

## Why This Step Exists Now

Context assembly is currently inline in `chat_service.py` and unreachable from any agent. [[AI Architecture]] names a Context Manager as a core component, and every later agent needs the same assembly logic that chat already has.

## Dependencies

- [[STEP-40 Tool Calling Capability]]

## Scope

- A context assembly component with a defined interface.
- Chat migrated onto it with no behaviour change.
- Bounded assembly — the existing window limit remains a spend control ([[CLAUDE|CLAUDE.md]] 15a).
- Extension points for the memory scopes that arrive next.

## Out of Scope

- No memory scopes yet.
- No retrieval — context is still assembled, not searched.
- No new user-visible behaviour.

## Surfaces Affected

**Backend:** `app/ai/context.py`, `chat_service.py` refactor.

## Required Tests and Proofs

- Chat behaviour is provably unchanged — the existing chat suite passes untouched.
- Assembly stays bounded.
- An agent can assemble context without importing the chat service.

## Definition of Done

Context assembly is a shared, bounded component, chat uses it with identical behaviour, and agents can use it too.

## Risks and Governance Gates

A pure refactor of a working path. The risk is behaviour drift, which the existing chat suite is the control against.

## Audit Gaps Closed

**Context Manager** — *Foundation / Partial, P1, no step*

---

## Navigation

- **Previous:** [[STEP-42 Chat Tool Actions]]
- **Next:** [[STEP-44 Memory Schema and Scopes]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
