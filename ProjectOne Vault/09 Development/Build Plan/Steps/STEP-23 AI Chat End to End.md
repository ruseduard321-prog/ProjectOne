---
title: STEP-23 AI Chat End to End
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-08
tags: [engineering, workflow, build-step, ai, frontend]
step_id: STEP-23
step_status: In Progress
detail_level: full
---

# STEP-23 — AI Chat End to End

**Status:** In Progress
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

### Where each was proven

| Validation | Proven by | Where it runs |
|---|---|---|
| Tenant isolation | `test_chat_isolation.py` — 12 tests against real policies | **CI only** (needs PostgreSQL — and see the note below: these errored on the first run) |
| Erasure end to end | `test_erasure_clears_conversations_and_messages`, `test_erasure_leaves_the_other_tenant_untouched` | **CI only** |
| Context bounded | `test_the_context_window_is_bounded`, `test_a_long_conversation_sends_no_more_than_the_window` | Local + CI |
| Provider failure honest | `test_a_provider_failure_raises_rather_than_fabricating_a_reply`, `test_a_failed_turn_still_keeps_the_users_question`; UI side in `chat/actions.test.ts` | Local + CI |
| Spend attributed | `AIService` `workflow_type="chat"`, metered by `test_ai_spend_isolation.py` | **CI only** |
| Loading / empty / error states | `loading.tsx`, `error.tsx`, `EmptyState` branches in `page.tsx` | Build + CI |

> [!example] What CI caught that this machine could not
> The `api` job failed **twice** on this step's PR, and both failures are worth recording — the second especially, because it is the more instructive.
>
> **Run 1 — the fixture never ran.** `test_chat_isolation.py` seeded from `identity.label`, an attribute `Identity` does not have. All **eleven** tests errored during setup, so not one isolation, erasure or role-vocabulary assertion executed.
>
> **Run 2 — the tests ran, and five failed.** Fixing the fixture revealed what it had been masking. Alice could read Bob's conversation and message, a cross-tenant UPDATE affected a row, and a message was editable by its author. Read at face value: a tenant breach.
>
> **It was not a breach.** The policies were correct from the start. `as_user` applies the tenant identity with `SET LOCAL ROLE` and a transaction-scoped `set_config` — both discarded immediately outside an explicit transaction, because psycopg autocommits each statement. Every query then ran as the privileged owner, which bypasses RLS entirely. The file's docstring claims it follows [[STEP-20 Projects Schema and Lifecycle|`test_project_isolation.py`]] exactly; that file wraps **16 of 16** `as_user` calls in a transaction, and this one wrapped **0 of 8**.
>
> **The negative control was the worst part.** It disabled RLS, observed a breach, and passed — but it would have passed identically against a harness that never applied an identity at all, because it only ever asserted the breach half. It now asserts both: zero rows visible with the policies in place, one with them disabled. *A control that cannot fail is not a control*, and this one was guarding the most security-sensitive assertions in the step.
>
> **No production code changed in either fix.** The migration's policies were right; the defect was entirely in how the tests exercised them.
>
> The lesson is not "the tests were wrong" but that **a skipped security test is indistinguishable from a passing one** in a local summary line — and worse, *a security test that runs without its identity applied looks like a passing one too*. CI ran **698 tests** against a real `postgres:17` where this machine manages 418. `PROJECTONE_REQUIRE_DATABASE_TESTS=1` is what makes that gap visible, and it is why a green `api` job — not a green local run — is what this step's isolation and erasure claims rest on.

> [!warning] The database-backed validation runs in CI, not on the development machine
> This machine has no PostgreSQL, no Docker, and `apps/api/.env` carries a redacted `DATABASE_URL` placeholder rather than a usable credential, so **285 database-backed tests skip locally**. CI provisions a throwaway `postgres:17` and sets `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, which turns those skips into hard failures — so a green `api` job is what actually proves isolation, erasure and spend metering.
>
> **The browser checklist below is therefore partly unverified.** The chat screen cannot be reached without a session, and a session cannot be created without the API, which cannot start without a database. What was verified in a browser is recorded honestly as such; what was not is named rather than assumed.

## Manual Browser Test Checklist

Recorded against a `next dev` server on `http://localhost:3000`, 2026-08-11.

| # | Check | Result |
|---|---|---|
| 1 | `/chat` requires a session — an unauthenticated request never reaches the route | **Pass.** Redirected to `/sign-in`; the dev server log shows no `/chat` entry at all, so the proxy refused it before the page ran. |
| 2 | The route compiles and is server-rendered on demand | **Pass.** `npm run build` lists `ƒ /chat` — dynamic, not statically prerendered, which is correct for a per-workspace screen. |
| 3 | No client-side console errors on the surfaces reachable without a database | **Pass.** `read_console_messages` returned no errors. |
| 4 | Signed-in empty state ("No conversations yet") | **Not verified in a browser.** Requires a session, which requires the API, which requires a database this machine does not have. Covered by the `conversations.length === 0` branch in `page.tsx` and exercised by the build. |
| 5 | Transcript renders a user/assistant exchange with attribution | **Not verified in a browser**, same reason. Covered by `chat-api.test.ts` attribution tests. |
| 6 | Composer pending state ("Sending…") during a turn | **Not verified in a browser**, same reason. Behaviour is `SettingsForm`'s, already shipped and exercised on the settings and projects screens. |
| 7 | A provider failure renders beside the transcript rather than replacing the screen | **Not verified in a browser**, same reason. Asserted in `chat/actions.test.ts` — 502/503 return an error state, `revalidatePath` is not called, and no reply is produced. |
| 8 | Loading skeleton shape matches the loaded screen | **Not verified in a browser**, same reason. `loading.tsx` mirrors the page's heading → list → transcript → composer structure by construction. |

**Items 4–8 need a database-backed environment to complete.** They are listed as outstanding rather than quietly omitted, and they are the reason this step is not `Done`.

## Definition of Done

A user holds a conversation with an AI inside their workspace, the conversation persists and is readable only by that workspace, context is bounded and includes the active project, spend is governed and attributed, erasure removes it all, and the screen defines loading, empty and error states.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI architecture, database schema, multi-tenancy, public API contract) and carries an **owner approval gate**.

### Completion state

Per [[Execution Protocol#Step Completion]], this step stays **`In Progress`** until every gate is satisfied:

- [x] Requirements implemented — all 8 tasks.
- [x] Local validation passed — api 418 passed, web 141 passed, lint/format/type-check/build clean.
- [x] Documentation updated in the same change.
- [ ] **Required CI green**, including the database-backed suite this machine cannot run.
- [ ] **Manual checklist items 4–8** completed in a database-backed environment.
- [ ] Review conversations resolved.
- [ ] **Owner approval** — this step carries a gate.

---

## Navigation

- **Previous:** [[STEP-22 Minimum Workflow Engine]]
- **Next:** [[STEP-24 Dashboard]]
- **Parent:** [[Build Plan]]
