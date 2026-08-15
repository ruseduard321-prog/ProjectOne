---
title: STEP-49 Richer Chat Context
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-49
step_status: Not Started
detail_level: outline
phase: "Context and Memory"
---

# STEP-49 — Richer Chat Context

**Status:** Not Started
**Phase:** Context and Memory — Shared context assembly and the five-scope Memory System, with the user controls CLAUDE.md §15 requires of it.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give AI Chat the context awareness its specification describes, now that memory exists.

## Why This Step Exists Now

[[AI Chat]] promises awareness of the workspace, active projects, previous conversations and long-term preferences. Today it sees one project's name and description plus twenty messages.

## Dependencies

- [[STEP-48 Memory Inspection and Control]]

## Scope

- Workspace, project and preference memory injected through the Context Manager.
- Cross-conversation context where the user's memory settings permit it.
- Project context extended beyond name and description — assets and recent workflow activity.
- Context budget still bounded and still a spend control.

## Out of Scope

- No channel context — channels do not exist yet.
- No analytics context — [[STEP-72 Analytics Metrics and Surfaces]] onward.

## Surfaces Affected

**Backend:** Context Manager consumers, chat service.

## Required Tests and Proofs

- Context respects memory disable settings.
- The budget still bounds total context, proven with a large memory store.
- Cross-conversation context never crosses a workspace.
- Cost per turn stays bounded as memory grows.

## Definition of Done

Chat is context-aware across workspace, project and preference memory, honouring user memory settings, inside a bounded spend envelope.

## Risks and Governance Gates

Spend risk: richer context means larger prompts on every turn. The budget is the control and must be verified under a realistic memory volume.

## Audit Gaps Closed

[[AI Chat]] context awareness — *Foundation / Partial, P1, no step*

---

## Navigation

- **Previous:** [[STEP-48 Memory Inspection and Control]]
- **Next:** [[STEP-50 Agent Invocation Safety Ceiling]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
