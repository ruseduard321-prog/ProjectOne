---
title: STEP-18 AI Cost Governance Controls
category: Development/Build Step
status: draft
version: "2.0"
last_updated: 2026-08-03
tags: [engineering, workflow, build-step, ai,backend,security]
step_id: STEP-18
step_status: Done
detail_level: full
---

# STEP-18 — AI Cost Governance Controls

**Status:** Done
**Detail level:** full — expanded by [[STEP-17 AI Router and Provider Abstraction]], per [[Execution Protocol]].

## Goal

Every [[CLAUDE|CLAUDE.md]] §15a control, built into the router rather than bolted on: budget ceilings, circuit breakers, retry limits, execution limits, usage monitoring, runaway-agent caps, emergency shutdown.

## Scope

§15a treats these as equivalent to a security requirement — skipping ahead is explicitly forbidden. Controls must be demonstrably **tripping under test**, not merely configured.

> [!success] The gate is now open
> [[STEP-17 AI Router and Provider Abstraction]] built the machinery that *makes* AI calls before the machinery that *bounds spend*. That inversion was only safe because STEP-17 shipped **no HTTP routes**. With this step `Done`, AI call paths may reach production, subject to the usual review — [[STEP-19 Settings and BYOK UI]] adds the first ones.

## Prerequisites

- [[STEP-17 AI Router and Provider Abstraction]] — `Done`

## Required Documentation

- [[CLAUDE|CLAUDE.md]] §15a
- [[AI Router Implementation]] — what STEP-17 actually built, and what it deliberately left to this step
- [[AI Providers]]

## Inherited from STEP-17

Recorded during expansion, while the context was loaded. **Read [[AI Router Implementation]] before starting** — these are the load-bearing facts, not a substitute for it.

- **Two ceilings already exist and are not this step's job.** `max_attempts_per_provider` (3) and `max_providers_tried` (2) multiply to bound one request at six upstream calls. They bound **runaway execution**; this step bounds **money**. Do not conflate them — a budget enforced by a class whose failure mode is "try the next provider" is not enforced.
- **A circuit breaker already exists, on availability.** `ProviderHealthTracker` removes a failing provider from rotation. §15a *also* requires a breaker on spend, and it must be a distinct mechanism: tripping on cost must stop the call, not route it elsewhere.
- **`TokenUsage` is already normalised across providers.** `CompletionResponse.usage` carries `prompt_tokens` / `completion_tokens` / `total_tokens` regardless of vendor, so spend accounting reads one shape. This was deliberate in STEP-17 precisely so this step needs no per-provider accounting code.
- **`cost_per_1k_tokens` is a selection input, not billing input.** It is a hardcoded indicative constant for comparing providers. Real spend must be computed from actual `TokenUsage`, not from this number.
- **`AIService.complete` is the single choke point.** Every AI call passes through it, and it already resolves the workspace. That makes it the natural place to attribute spend — and the natural place a bypass would be invisible, so any new call path must be checked against it.
- **The health tracker is in-process and per-worker.** Budget state must **not** copy that approximation: N workers each permitting the full budget means N× the ceiling, which for money is a defect rather than an approximation. Budget state needs the database, or an ADR for a shared store.

## Tasks

1. **Persist spend per workspace.** A new tenant-scoped table, with RLS in the same migration ([[RLS Policy Pattern]]). Record at minimum: workspace, provider, model, token counts, computed cost, and the workflow type that incurred it. Written from the verified `TokenUsage` on the response, never estimated.
2. **Enforce a configurable ceiling per workspace and per workflow type**, checked *before* the call. A ceiling checked afterwards is an invoice, not a limit.
3. **Build the spend circuit breaker** — distinct from `ProviderHealthTracker`. It stops the call rather than rerouting it, and it trips on cost rather than on failures.
4. **Add runaway-agent protection**: a hard, low cap on chained or recursive invocations, independent of and additional to the retry ceiling.
5. **Add wall-clock and total-token execution limits per run**, independent of the retry ceiling. A workflow hitting a ceiling **fails loudly**; it does not silently continue.
6. **Emit usage metrics with anomaly detection** against each workspace's own baseline ([[CLAUDE|CLAUDE.md]] §26 — this is observability, not an optional dashboard).
7. **Build the emergency shutdown path**: disable AI spend for one workspace, one workflow type, or the whole platform, **without a code deploy**. Infrastructure, not a hypothetical.
8. **Make degradation graceful and honest.** A tripped ceiling produces a clear message and a safe fallback — never a silent failure, and never an ignored ceiling to keep a feature working.

## Validation

- **Every control is observed tripping**, not merely configured. A control whose test only asserts it is *present* asserts nothing.
- **The budget ceiling blocks a call that would exceed it**, proven with an exact assertion on whether the provider was invoked.
- **Spend is attributed to the correct workspace**, and a cross-tenant read of spend records is proven blocked — following [[RLS Policy Pattern]], with the policies-removed negative control.
- **The recursion cap holds** against an agent that tries to re-trigger itself, asserted on exact invocation count.
- **Emergency shutdown works without a restart**, demonstrated.
- **A tripped ceiling surfaces honestly** to the caller — asserted on the response, not on a log line.
- **Negative controls**: remove each ceiling in turn and confirm the specific tests fail. A ceiling whose removal breaks nothing was never enforcing anything.
- Lint, type-check, tests and build pass for `apps/api` in CI.

## Definition of Done

Every §15a control exists, is enforced before spend rather than after, and has been observed tripping under test: per-workspace and per-workflow budget ceilings, a spend circuit breaker distinct from the availability breaker, runaway/recursion caps, execution limits, near-real-time usage tracking with anomaly alerting, and a deploy-free emergency shutdown. Spend records are RLS-protected tenant data. A tripped control degrades gracefully and says so.

**This is a Critical change** ([[CLAUDE|CLAUDE.md]] §21 — AI architecture, database schema, security controls, multi-tenancy) and carries an **owner approval gate**.

**On completion, the STEP-17 gate opens**: AI call paths may reach production, subject to the usual review.

---

## Outcome

Completed 2026-08-03. Architecture and reasoning: [[AI Cost Governance]]. Schema: [[Table - ai_spend_records]] · [[Table - ai_budgets]] · [[Table - ai_shutdown_switches]].

### The central decision

**A ceiling checked after the call is an invoice**, and the cost of a call is unknowable until after it returns. Resolved with **reserve → call → settle**: a pessimistic worst case is reserved atomically before the call and adjusted to the real figure afterwards.

Three shapes were considered. Aggregating the ledger per check (`SELECT sum(cost)`) is correct but scans an unbounded table on every call *and* races. An in-process counter was refused outright by STEP-17's inherited note — N workers each permitting the full budget is N× the ceiling, which for money is a defect rather than an approximation. The chosen shape is a budget row with a **compare-and-increment in one statement**, so PostgreSQL's row lock settles concurrency rather than application logic that would have to be right on every path.

### What was found by running it, not by reviewing it

- **Six database connections per governed AI call**, against a Supabase session pooler limited to 15 — two concurrent calls would exhaust the pool and the third would fail to connect, turning a cost control into an availability failure. Observed as `EMAXCONNSESSION` during the concurrency test. `AISpendRepository.session()` collapses it to **one**, measured (6 → 1) rather than reasoned about, and guarded by a test.
- **A governance refusal would have surfaced as HTTP 500.** No handler was registered, so a deliberate, correct control would have reached the client as a server crash. Now 402 for a budget or execution limit, 503 + `Retry-After` for a shutdown or breaker.
- **`provider_credentials` was never registered for export or erasure** — a gap inherited from STEP-17, meaning a workspace erasure silently left encrypted provider keys behind ([[CLAUDE|CLAUDE.md]] §16). Fixed alongside registering this step's own spend store, since adding one while leaving the sibling broken would knowingly ship a §16 violation.
- **Two test defects of my own**, both worth recording because the lesson generalises: an anomaly test asserted a return value that conflated *detection* with *tripping* (a workspace with no budget row has no breaker to trip), and a baseline-window test asserted a total under a threshold when the real property is that the spike is **absent from the baseline window** — the first version was testing the fixture's size.

### The evidence

**The negative controls, not the passing suite.** Each control's absence is reproduced and the breach observed: enforcement-after-the-call still spends, a read-then-write check admits two calls that together breach the ceiling, an unsettled reservation stays charged, an uncapped chain runs 50 calls, a mis-scoped switch stops nothing, a zero rate makes an unknown model free.

**Against a live database, 34 checks passed**, including the two properties a fake structurally cannot demonstrate:

- **Atomicity:** twenty concurrent threads reserving $1 against a $10 ceiling — exactly ten granted, running total landing on `10.000000` precisely.
- **Isolation:** another tenant's spend invisible, forging a record refused, rewriting refused, deleting refused, the platform switch invisible and uncreatable — with RLS disabled mid-test to observe the breach and restored afterwards.

All probe rows removed and the database confirmed back to its prior contents by query. Migration verified reversible (`downgrade` then `upgrade`).

### Deliberate limitations

- **An owner can currently zero their own `spent_usd`.** PostgreSQL policies are per-row, not per-column, and the UPDATE policy must exist for configuration. The mitigation is that the immutable ledger — not this counter — is what a billing reconciliation reads. `test_a_tenant_cannot_clear_its_own_running_total` documents the exposure honestly rather than asserting a protection that does not exist. Closing it is a column-level grant belonging to [[STEP-19 Settings and BYOK UI]].
- **No budget is configured by default**, so a new workspace is unmetered. Refusing every call on a platform that has not asked anyone to set a limit is the wrong default; whether it stays that way is a launch decision ([[STEP-25 Launch Readiness Criteria]]).
- **Anomaly detection runs inline** after each recorded call, adding two queries to the settle path. Near-real-time as §15a requires; a background evaluation is the natural evolution once a scheduler exists.
- **Alerting is an `ERROR` log line**, not a pager. Routing it is infrastructure ([[Infrastructure]]), not application code.
- **`test_ai_spend_isolation.py` (30 tests) is skipped by design** without `PROJECTONE_TEST_DATABASE_URL` — it creates and destroys rows, so it belongs in CI against a throwaway container, never the development project. Its coverage was obtained here by the live behavioural proof above.

---

## Navigation

- **Previous:** [[STEP-17 AI Router and Provider Abstraction]]
- **Next:** [[STEP-19 Settings and BYOK UI]]
- **Parent:** [[Build Plan]]
