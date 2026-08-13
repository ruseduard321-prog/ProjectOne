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
| A message is immutable, including while being deleted | `test_a_message_cannot_be_rewritten_while_being_soft_deleted`, `test_no_attributed_field_survives_a_soft_delete` (5 fields), `test_an_ordinary_message_soft_delete_is_still_permitted` | **CI only** |
| A client-supplied id cannot reach another tenant | `test_a_client_supplied_id_cannot_adopt_another_tenants_conversation`, `test_another_tenants_conversation_is_not_continuable` | CI / Local |
| A failed first turn is reachable, and a retry does not duplicate it | `test_retrying_with_the_same_id_continues_one_conversation`; UI side in `chat/actions.test.ts` | Local + CI |
| **A stored question survives a provider failure** | `test_a_stored_question_survives_a_provider_failure`, `test_a_claim_survives_a_rolled_back_request_transaction` | Local + **CI only** for the transaction half |
| **Concurrent completions invoke a provider once** | `test_only_one_of_many_concurrent_callers_may_invoke_a_provider` (4 real threads) | **CI only** |
| A superseded claim cannot settle a turn | `test_a_superseded_claim_cannot_settle_the_turn` | **CI only** |
| One turn admits one reply, even after deletion | `test_one_turn_admits_one_reply_even_after_it_is_deleted` | **CI only** |
| A reply must answer a user message in its own conversation | `test_a_reply_must_answer_a_user_message_in_its_own_conversation` | **CI only** |
| Another tenant's turn cannot be claimed | `test_another_tenants_turn_cannot_be_claimed` | **CI only** |
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

> [!bug] What review caught that green CI could not
> Two defects survived a fully green pipeline and were found by independent review of the merged diff. Both are worth recording, because neither was the kind of thing another test run would have surfaced.
>
> **1. Message immutability was asserted, not enforced.** `messages_soft_delete_member` carries `WITH CHECK (deleted_at IS NOT NULL)`, and the migration's own docstring claimed this made a transcript immutable — "rewriting `content` is still refused by the policy rather than by convention". **It did not.** A `WITH CHECK` constrains the *resulting* row, and that clause constrains exactly one column of it. A single `UPDATE` setting `content` **and** `deleted_at` satisfies the policy completely. The policy permitted rewriting history as long as the rewrite also deleted it.
>
> The test that was supposed to prove immutability (`test_a_message_cannot_be_edited_by_its_author`) updated `content` *alone*, which the policy genuinely does refuse — so it passed while testing the one variation that was never the risk.
>
> **RLS structurally cannot express this rule.** A policy sees only the candidate row, never the row it replaces; "content must equal what it was" is a claim about `OLD` and `NEW` together. A `BEFORE UPDATE` trigger is PostgreSQL's mechanism for that comparison, and `workspace_members` already uses one for the last-owner rule — the same shape of invariant. `app_messages_immutable` now refuses any UPDATE changing anything except `deleted_at`, `updated_at` and `version`, expressed as a **whitelist** so a column added later is immutable by default.
>
> **2. A failed first turn saved the user's question somewhere unreachable.** The conversation id existed only inside a successful response. So a first message that failed at the provider persisted the conversation *and* the question under an id the UI never learned — the screen said "your message was saved" while showing no conversation open, and retrying created a **second** conversation holding a **second** copy of the question. Every individual piece behaved as documented; the defect was in the seam between them.
>
> Fixed by letting the client choose the conversation id up front, so the id is known before the call rather than discovered after it. Success navigates there, failure navigates there carrying the reason, and a retry names the conversation that already exists.
>
> **The common thread is that both defects were invisible to the tests that covered them.** The first had a passing test asserting the adjacent property; the second had passing tests on both sides of a seam neither crossed. Green CI proves the assertions that were written, and says nothing about the ones that were not.
>
> **A footnote worth keeping.** Adding the trigger made `test_a_message_cannot_be_edited_by_its_author` fail in CI — it expected `InsufficientPrivilege` from the policy, and a BEFORE trigger runs before a policy's `WITH CHECK` is evaluated, so `CheckViolation` arrived instead. The edit was refused either way; only the layer doing the refusing moved. The test now accepts either, because its property is *"an edit is refused"* and pinning it to one exception would make it fail if the **other** guard were removed — backwards for a test whose job is to notice that removal. Confirmed against PostgreSQL 17.6 rather than inferred.

> [!warning] What this machine can and cannot validate
> **Correcting an earlier claim in this note.** A previous revision said `apps/api/.env` carried a redacted `DATABASE_URL` placeholder and that no database was reachable. That was wrong: `.env` holds working credentials for the **shared Supabase development project** (`aws-0-eu-central-1.pooler.supabase.com`, PostgreSQL 17.6), and the API starts and serves `/health` against it. The mistake made items 4–8 look blocked by infrastructure when they are blocked by something narrower.
>
> What that database *did* prove, directly and with every write rolled back: the immutability defect was **live and reproducible** there (an `UPDATE` setting `content` and `deleted_at` together succeeded and changed the stored text), and `b4e8c02d71fa` closes it while leaving ordinary soft deletion working.
>
> **The RLS isolation suite still runs in CI only, and deliberately so.** It requires `PROJECTONE_TEST_DATABASE_URL` — a variable distinct from `DATABASE_URL` — and refuses to run without it. That guard exists precisely so a suite that creates and destroys tenant fixtures cannot be pointed at a shared database by accident. It was not overridden. CI provisions a throwaway `postgres:17` with `PROJECTONE_REQUIRE_DATABASE_TESTS=1`, and a green `api` job is what proves isolation, erasure and spend metering.

> [!bug] What manual testing caught that a green pipeline could not
> Item 7a failed against a real browser, and the diagnosis is the most instructive thing in this step.
>
> **The symptom.** Removing the provider key and sending a message produced the correct inline error — *"Your message was saved — try sending it again in a moment"* — and the URL moved to a new `?conversation=` id. But the screen showed *"No conversation open"*, the conversation list did not contain it, and the saved question was nowhere. The database confirmed it: **the conversation did not exist and the question was never persisted.**
>
> **The cause was the transaction boundary, not the chat code.** `ChatService` persisted the question *before* calling the provider — the ordering was right. But `RequestSessionFactory.authenticated_as` wraps the **entire request** in one transaction, so when the provider error propagated out, PostgreSQL rolled back the conversation and the message along with it. The promise the UI made was one the architecture could not keep.
>
> **It could not be fixed by committing mid-request.** psycopg refuses `commit()` inside a `Transaction` context outright, and — verified against the live database — a commit *discards* `SET LOCAL ROLE`, so the request would continue as the privileged owner with RLS switched off. The obvious fix was a tenant-isolation breach.
>
> **So a turn became two requests**: `POST /chat/conversations` stores the question and commits, then `POST /chat/conversations/{id}/completion` answers it. Step 1 contacts no provider, so what it stores survives whatever step 2 does.
>
> **The second design was also wrong, and review caught it.** The first attempt at making completion idempotent used a unique index on the reply. A concurrency probe showed *both* callers reading zero replies and *both* proceeding to invoke the provider — the index refuses the duplicate **row**, after the duplicate **charge**. Deduplicating storage is not deduplicating spend. The mechanism is now an atomic conditional claim (`WHERE turn_status = 'pending'`), committed before the network call: four concurrent callers, **one** invocation.
>
> **The common thread across all four defects in this step**: every one was invisible to the tests covering it, because the fakes have no transactions and no concurrency. `test_a_failed_turn_still_keeps_the_users_question` passed throughout, against a dict. That is why `test_chat_turn_claims.py` exists and why it is CI-only.

> [!bug] The third manual finding: a retryable turn nothing could reach
> Item 7b failed, and it failed *because* 7a's fix worked. The question survived the provider failure exactly as promised — and then nothing on the screen could name it.
>
> **The symptom.** Three failed sends left three identical `pending` questions in one conversation, each stored correctly, none with a reply, and none distinguishable in the transcript from an answered one. The database was right; the screen was silent.
>
> **The cause was a field that stopped at the API.** `turn_status` was written by the first migration, read by `ConversationRepository`, and then simply not carried by `MessageResponse`. The transcript therefore rendered an unanswered question identically to an answered one, and every "retry" went through `sendMessageAction` — which begins with `startChatTurn` and so **stores a new question every time**. A resend is a new send; there was no path that answered a turn that already existed.
>
> **Why the guarantee was technically kept and practically worthless.** The contract said a failed turn is retryable, and it was: the claim was released, the row was `pending`, the completion endpoint would have answered it. But nothing rendered the state and nothing offered the id, so the only reachable action created a fourth question instead of answering the first. *A turn that is retryable by contract and invisible on screen is not retryable in any sense the user can use.*
>
> **The fix is small because the state already existed.** `turn_status` is carried through to the client, the transcript marks any non-`completed` question as unanswered, and a `retryTurnAction` calls **only** the completion endpoint for a `user_message_id` the transcript already holds. No new user message, same conversation id, same turn key.
>
> **The pattern, for the fourth time in this step:** every test passed. `test_chat_turn_claims.py` proved the turn was claimable; `actions.test.ts` proved a failure reported honestly. Neither could see that the two halves never met, because no test rendered a `pending` question and asked what a user could do about it.

## The two-request contract

A turn is two calls, and the split is load-bearing rather than stylistic.

| Step | Endpoint | Contacts a provider | On failure |
|---|---|---|---|
| 1 | `POST /workspaces/{id}/chat/conversations` | No | Nothing stored; the question is not lost because it was never accepted |
| 2 | `POST /workspaces/{id}/chat/conversations/{id}/completion` | **Yes** | Question stays stored; claim released; turn retryable |

**The turn key is the user message id, not the conversation id.** A conversation holds many turns; keying idempotency on the conversation would make a legitimate follow-up question look like a retry of the previous one and refuse it.

### Sending and retrying are different operations

This distinction is the fix for the third manual finding, and it is worth stating precisely because the two look identical on screen:

| | Sending | Retrying |
|---|---|---|
| Action | `sendMessageAction` | `retryTurnAction` |
| Calls | `startChatTurn`, then `completeChatTurn` | `completeChatTurn` **only** |
| New user message | Yes — a resend is a new question | **No** |
| Turn key | Freshly minted | The existing `user_message_id` |
| Offered when | Always | Only on a `pending` question |

**A question's state is visible in the transcript**, because a state the user cannot see is one they cannot act on:

- **`pending`** — rendered as unanswered, with a **Retry** control. No provider holds the turn.
- **`in_progress`** — rendered as being answered, with **no** Retry. A call is in flight, or a process died holding the claim; without a lease the two are indistinguishable, and offering a button that may pay twice is worse than offering none. The message says to contact support if it persists.
- **`completed`** — nothing rendered. Annotating the ordinary case would bury the exceptional one.

**Concurrency is the server's, not the button's.** Nothing serialises a double click, and nothing needs to: the claim is a conditional UPDATE committed before any network call, so one Retry wins and the rest receive 409 — reported as *"already being answered"* rather than as a failure inviting another click. The guarantee has to hold against two browsers regardless, so a client-side guard would only hide the second click, never remove the race.

### Guarantees, stated exactly

- **Concurrency — at most one provider invocation per question.** Proven with four concurrent callers against real PostgreSQL.
- **Ordinary failure — fully retryable.** The claim is released, the question stays stored, no charge is incurred (the reservation is settled by `AIService`'s existing `finally`).
- **Crash after the provider accepted — not recoverable automatically, by design.** The turn stays visibly `in_progress` and answers 409. Returning it to `pending` on a timer would re-invoke a provider that has already charged for the request. **Exactly-once execution across a crash is unachievable without provider-side idempotency keys**, and this step does not pretend otherwise.

### Follow-up required: AI execution durability (ADR-backed, not yet scheduled)

Four concerns were deliberately left out of this step because they belong to the AI layer as a whole, not to chat, and because each is an architectural decision rather than a fix:

1. **Provider-side idempotency.** OpenAI accepts an `Idempotency-Key` header. Adopting it would close the crash window this step cannot — but it changes `AIProvider`, so it governs every AI call and needs verifying against each provider's official documentation rather than assumed.
2. **Stale-claim reconciliation.** How an operator resolves a turn stuck `in_progress`, and whether that is manual, assisted or automatic.
3. **Lease policy and bounded recovery.** What a safe lease duration is, and what may be retried automatically once provider idempotency exists.
4. **Crash-window handling across all AI features.** Workflow runs have the same exposure; chat is simply where it surfaced first.

**This is an ADR before it is a step** — it reverses nothing, but it constrains how every future AI feature executes. Until it lands, the honest position is the one this step ships: a stuck turn is visible, says so, and is not silently retried.

### The spend invariant

Spend is **not** in one transaction with the reply, and reversing that would undo a deliberate STEP-22 decision — a budget row locked for the duration of an upstream HTTP call is how one becomes a bottleneck. What holds instead:

- every reservation is eventually settled or released;
- no successful assistant reply exists without recorded spend;
- an ordinary provider failure leaves no charge.

## Manual Browser Test Checklist

Recorded against a `next dev` server on `http://localhost:3000`, 2026-08-11.

| # | Check | Result |
|---|---|---|
| 1 | `/chat` requires a session — an unauthenticated request never reaches the route | **Pass.** Redirected to `/sign-in`; the dev server log shows no `/chat` entry at all, so the proxy refused it before the page ran. |
| 2 | The route compiles and is server-rendered on demand | **Pass.** `npm run build` lists `ƒ /chat` — dynamic, not statically prerendered, which is correct for a per-workspace screen. |
| 3 | No client-side console errors on the surfaces reachable without a database | **Pass.** `read_console_messages` returned no errors. |
| 4 | Signed-in empty state ("No conversations yet") | **Pass**, 2026-08-12. |
| 5 | Transcript renders a user/assistant exchange with attribution | **Pass.** Automatic navigation to the new conversation, both bubbles, provider/model/token metadata shown. |
| 6 | Composer pending state ("Sending…") during a turn | **Not clearly observed.** The turn completed faster than the pending state could be seen. Behaviour is `SettingsForm`'s, already shipped on settings and projects. |
| 7a | A provider failure renders beside the transcript, keeping the saved question | **Pass**, 2026-08-13 22:16 (request `f2a30fd3`). Failed first, then fixed by the two-request split, then confirmed against a real forced outage. Honest 502 after three bounded attempts, question visible, Retry beneath it, conversation id unchanged. **No spend recorded.** |
| 7b | **Retry answers the existing question** — same conversation id, same user message id, no second question stored | **Pass**, 2026-08-13 22:18 (request `e8692489`). Retry pressed, not Send: no `POST /chat/conversations` ran, so no second question was stored. One provider call, one reply (`cc5ebaa1`) linked to the same question (`b23f9faf`), turn `completed`, claim cleared, one spend record. |
| 8 | Loading skeleton shape matches the loaded screen | **Partial.** Persistence after a hard refresh passed; the skeleton itself was too brief to observe. |

### What the forced-outage retest proved

Items 7a and 7b were re-run on 2026-08-13 against a genuine provider outage, forced by pointing `api.openai.com` at `127.0.0.1` in the Windows hosts file. Both passed, and the evidence is worth recording because this is the pair that failed twice.

| Property | Evidence |
|---|---|
| Same question reused | `b23f9faf` stored once at 22:15:59; no `POST /chat/conversations` between the 22:16 failure and the 22:18 retry |
| Exactly one reply | `cc5ebaa1` — the only row whose `reply_to` names that question |
| Turn settled cleanly | `turn_status = completed`, `claim_token` NULL |
| One invocation, one charge | One `200 OK` to OpenAI, one spend record (527 tokens, $0.021940) |
| Failure cost nothing | Three bounded attempts, breaker tripped, 502 — **no `ai_spend_recorded`** |

`claimed_at` remains populated on a completed turn by design: the migration keeps it as an operator diagnostic, and only `claim_token` is cleared on settle.

**Two failure-injection methods were tried, and only one works.** Restricting the OpenAI key's *Threads* scope does not affect `/v1/chat/completions` (that is governed by model capabilities, and a scope refusal would be `403` anyway). A hosts-file redirect does work — but on Windows the hosts file may carry the **ReadOnly** attribute, in which case `Add-Content` fails *silently* and the block appears applied while DNS still resolves normally. Verify with `Select-String` before trusting it; an unverified block produced two false "bypass" reports during this step.

### What remains open

**Items 4, 5, 7a and 7b passed.** Items 6 and 8 are *not clearly observed* rather than failing: both are transient visual states (the composer's "Sending…" and the route's loading skeleton) that completed faster than they could be seen. The behaviour is `SettingsForm`'s and `loading.tsx`'s, already shipped and observed on the settings and projects screens.

**Test data was removed after the retest.** Both test conversations and all 13 messages are deleted; `conversations` and `messages` are empty. The five `ai_spend_records` were **deliberately kept** as the audit trail for the §15a invariant — one charge per successful call, none for any failure — along with the workspace, its membership, the project, the BYOK credential and the $1.00 USD ceiling.

Final spend across the whole step: **5 records, $0.037280 USD**, against a **$1.00 USD** ceiling. Every successful call is charged exactly once; no failed call is charged at all.

**The platform's spend unit is USD throughout**, and this note previously said "€1" in error. The ledger column is `ai_spend_records.cost_usd`, the ceiling is `ai_budgets.limit_usd`, and the Settings field is labelled *Spending limit (USD)* — there is no currency conversion anywhere in the system, and no other unit is stored. A ceiling written in another symbol would misstate what was actually configured and enforced.

## Definition of Done

A user holds a conversation with an AI inside their workspace, the conversation persists and is readable only by that workspace, context is bounded and includes the active project, spend is governed and attributed, erasure removes it all, and the screen defines loading, empty and error states.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI architecture, database schema, multi-tenancy, public API contract) and carries an **owner approval gate**.

### Completion state

Per [[Execution Protocol#Step Completion]], this step stays **`In Progress`** until every gate is satisfied:

- [x] Requirements implemented — all 8 tasks.
- [x] Local validation passed — api 423 passed, web 163 passed, lint/format/type-check/build clean.
- [x] Documentation updated in the same change.
- [x] Message immutability enforced by `b4e8c02d71fa`, proven against the live development database.
- [x] First-turn navigation and retry made coherent, with tests on both sides.
- [x] A failed turn is visible and retryable *on screen*, answering the existing question rather than asking a new one.
- [x] **Required CI green** on `8895962` — all three jobs, including the database-backed `api` suite this machine cannot run.
- [x] **Manual checklist items 4, 5, 7a, 7b** — passed against a real database and a genuine forced provider outage. Items 6 and 8 are transient visual states that could not be observed; behaviour is shared with already-shipped screens.
- [x] Test data removed; spend audit trail retained deliberately.
- [ ] Review conversations resolved.
- [ ] **Owner approval** — this step carries a gate.

---

## Navigation

- **Previous:** [[STEP-22 Minimum Workflow Engine]]
- **Next:** [[STEP-24 Dashboard]]
- **Parent:** [[Build Plan]]
