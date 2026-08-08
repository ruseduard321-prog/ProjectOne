---
title: STEP-23 AI Chat End to End
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, ai, frontend]
step_id: STEP-23
step_status: Not Started
detail_level: full
---

# STEP-23 — AI Chat End to End

**Status:** Not Started
**Detail level:** full — expanded by [[STEP-22 Minimum Workflow Engine]], per [[Execution Protocol]].

## Goal

The conversational interface — proof that AI layer, workflow engine, auth and frontend work together end to end.

## Scope

Conversation Memory layer only; Project/Channel/Workspace/User Preference memory is later. Context limited to active project plus current conversation.

**This is the first user-facing AI surface**, and the first where a user's own words are stored. Both make [[CLAUDE|CLAUDE.md]] §16 (data ownership, erasure) and §15 (AI never pretends certainty) central rather than incidental.

**Out of scope:** the four other memory scopes, agent tool-use inside chat, chat-triggered workflows, and file attachments.

## Prerequisites

- [[STEP-22 Minimum Workflow Engine]] — `Done`, and owner-approved (it carries an approval gate)

## Required Documentation

- [[AI Chat]] — the product specification
- [[Memory System]] — what conversation memory is, and its erasure obligations
- [[API Conventions]] — the contract every new route joins
- [[Design System]] — the UI standard

**Reference only:** [[Design Backlog and UI Vision]]. It binds nothing.

## Inherited from STEP-22

Recorded during expansion, while the context was loaded.

- **`AIService.complete` is the only sanctioned path to a provider**, and already enforces shutdown, breaker, budget, and `ExecutionBudget`. Chat calls it exactly as the planning agent does. `test_no_ai_call_path_bypasses_governance` asserts nothing else reaches `AIRouter`.
- **`workflow_type` defaults to `"chat"`** in `AIService` (`DEFAULT_WORKFLOW_TYPE`), so chat spend already has a bucket. Per-workflow ceilings meter on it.
- **`AIProvider` has no streaming method**, deliberately — its docstring names this step as the owner of chat's transport. Adding streaming is a method on the ABC plus one implementation per provider, and is a real decision: it changes the response contract, the governance settle point (tokens are known only at the end), and the error path mid-stream.
- **A new tenant table ships its RLS policy in the same migration**, must be added to `_WORKSPACE_DEPENDANTS` **in dependency order** (that list is no longer alphabetical — see [[Table Conventions]]), and must be registered in `REGISTERED_STORES`.
- **A SELECT policy must never filter `deleted_at IS NULL`.** Four steps have now dealt with this; two paid a step each for getting it wrong, two got it right at creation time.
- **Wherever the database constrains a value to a set, the outermost schema enumerates the same set** — a message `role` column is exactly this shape.
- **An error status describes the request; a resource's state describes the outcome** ([[API Conventions]]). A completion that fails is not automatically a 5xx.
- **The web app still resolves the caller's first workspace** and has no switcher.

## Tasks

1. **Migration** — conversation and message tables. Standard column set, RLS enabled *and* forced, per-command policies, `text` + CHECK for the message role vocabulary, composite FK binding a message to its conversation's workspace. Register in `_WORKSPACE_DEPENDANTS` in dependency order.
2. **Erasure stores** — both tables in `REGISTERED_STORES` in the same change. **A user's own words are the clearest case of data they own** ([[CLAUDE|CLAUDE.md]] §16).
3. **Repository and service** — `ChatService` owning conversation history assembly and the context window. Business logic never in a router.
4. **Context assembly** — the current conversation plus the active project. Bounded: a window that grows without limit is a cost control failure before it is a quality one.
5. **Routes** — list conversations, read one with its messages, post a message, delete a conversation. `requires(VIEW_WORKSPACE)`; rate limited per user on the message route.
6. **Transport decision** — streaming or not. **State it explicitly rather than defaulting**: it changes the response contract, where spend is settled, and how a mid-stream failure is reported. Non-streaming is a legitimate first answer.
7. **UI** — a chat screen with loading, empty and error states, per [[Design System]].
8. **Tests** — isolation through the route layer, erasure end to end, context bounded, and a provider failure surfacing honestly rather than as a confident empty answer.

## Validation

- **A conversation and its messages cannot be read across the tenant boundary**, proven against real response bodies.
- **Erasure removes conversations and messages**, asserted end to end — including that the soft delete actually affects rows.
- **The context window is bounded**, asserted rather than assumed.
- **A provider failure surfaces honestly** — no fabricated reply, no silent empty message.
- **Chat spend is attributed and metered**, proven against the ledger as STEP-22 did.
- Every new screen renders its loading, empty and error states.
- Lint, type-check, tests and build pass for both apps in CI.

## Definition of Done

A user holds a conversation with an AI inside their workspace, the conversation persists and is readable only by that workspace, context is bounded and includes the active project, spend is governed and attributed, erasure removes it all, and the screen defines loading, empty and error states.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI architecture, database schema, multi-tenancy, public API contract) and carries an **owner approval gate**.

---

## Navigation

- **Previous:** [[STEP-22 Minimum Workflow Engine]]
- **Next:** [[STEP-24 Dashboard]]
- **Parent:** [[Build Plan]]
