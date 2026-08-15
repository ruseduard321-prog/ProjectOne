---
title: STEP-42 Chat Tool Actions
category: Development/Build Step
status: draft
version: "1.1"
last_updated: 2026-08-15
tags: [engineering, workflow, build-step, ai, backend]
step_id: STEP-42
step_status: Not Started
detail_level: outline
phase: "AI Capability Expansion"
---

# STEP-42 — Chat Tool Actions

**Status:** Not Started
**Phase:** AI Capability Expansion — Turning a chat-only AI layer into one that can produce media and take actions, with every prompt versioned before the agents that depend on them are written.
**Detail level:** outline — goal, scope and dependencies only. Expanded to full detail by the step immediately preceding it, per [[Execution Protocol]].

## Objective

Give AI Chat a real, small set of tools so a user can act through conversation.

## Why This Step Exists Now

[[AI Chat]]'s core capabilities — create and manage projects, trigger workflows — become reachable the moment tool calling exists. Starting small proves the approval UX before the tool surface grows.

## Dependencies

- [[STEP-40 Tool Calling Capability]]
- [[STEP-26 Product Design System Foundation]]

## Scope

- A small set of tools: create a project, transition a project, start a workflow, read project state.
- An in-chat approval surface showing exactly what will happen before it happens.
- Tool results rendered honestly in the transcript, including failures.
- Every mutating tool gated by default.

## Out of Scope

- No publishing, billing or destructive tools.
- No autonomous execution mode.

## Surfaces Affected

**Backend:** tool implementations over existing services. **Frontend:** chat approval and result rendering.

## Required Tests and Proofs

- A mutating tool call requires explicit approval in the UI before anything changes.
- Rejecting a tool call leaves state untouched.
- A failed tool call is shown as failed, never summarised as success.
- Tools respect existing permissions and tenant boundaries.

## Definition of Done

A user can create a project, transition it and start a workflow through chat, approving each action explicitly, with honest rendering of every outcome.

## Risks and Governance Gates

**Critical** — AI acting on user data through a conversational surface. The approval UI is the control; a confusing one is a safety defect, not a design nitpick.

## Audit Gaps Closed

[[AI Chat]] create/manage projects and trigger workflows — *Missing, P1*

---

## Navigation

- **Previous:** [[STEP-41 Prompt Store and Versioning]]
- **Next:** [[STEP-43 Shared Context Manager]]
- **Parent:** [[Build Plan]]
- **Related Notes:** [[Product Coverage Audit]] · [[Execution Protocol]]
