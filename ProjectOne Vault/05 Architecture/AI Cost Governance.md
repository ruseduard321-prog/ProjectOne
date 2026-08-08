---
title: AI Cost Governance
category: Architecture
status: stable
version: "1.2"
last_updated: 2026-08-04
tags: [ai, backend, architecture, security, cost, standards]
aliases: ["Spend Governance", "AI Budgets", "Cost Controls"]
---

# AI Cost Governance

**How ProjectOne stops an AI feature from spending money it should not**, established by [[STEP-18 AI Cost Governance Controls]] and binding from that point on.

[[CLAUDE|CLAUDE.md]] §15a specifies *what* must exist — budget ceilings, circuit breakers, retry limits, execution limits, usage monitoring, runaway caps, emergency shutdown. This note records *how* it is built and which decisions are now settled.

> [!important] The STEP-17 gate is now open
> [[AI Router Implementation]] built the machinery that *makes* AI calls before the machinery that *bounds spend*, which was only safe because nothing user-facing called it. With this step `Done`, AI call paths may reach production, subject to the usual review.

## The One Property Everything Else Serves

**A ceiling checked after the call is an invoice.** Every design decision below follows from that: the shutdown check, the breaker check and the budget reservation all complete *before* any provider is contacted, and the tests assert `provider.calls == 0` rather than merely asserting that an exception was raised.

An exception-only assertion would pass just as happily against enforcement that ran after the money was spent.

## The Ordering

```
1. Emergency shutdown    is spending disabled at all?
2. Spend breaker         has this workspace been stopped for review?
3. Budget reservation    is there room under every applicable ceiling?
   -> THE PROVIDER CALL HAPPENS HERE, AND ONLY HERE
4. Settlement            replace the reservation with the real cost
5. Ledger + anomaly      record it, compare against the baseline
```

Cheapest and most absolute first. A shutdown is not reachable only by workspaces that happen to have budget left, so it is checked before the budget — asserted by `test_shutdown_is_checked_before_the_budget`.

## Reserve, Then Settle

The hard problem: a budget must be enforced **before** the call, and the cost of a call is unknowable **until after** it returns.

So spend is **reserved** at a pessimistic worst case before the call and **settled** to the real figure afterwards:

| | Reserved | Actual |
|---|---|---|
| Basis | full `max_tokens`, unknown-model rate if unnamed | provider's own reported `TokenUsage` |
| When | before the call | after it returns |

Between those two moments the workspace is charged more than it has spent, which is the **safe direction**: a concurrent call sees the pessimistic figure and is refused, rather than seeing an optimistic one and overshooting.

> [!warning] The settlement runs in a `finally`, and that is not stylistic
> A reservation released only on success leaks on exactly the failure paths nobody watches, permanently shrinking a workspace's ceiling with no error anywhere. `AISpendService.guard()` is a context manager precisely so a caller **cannot** take the reservation without also getting the settlement — `reserve()`/`settle()` as a public pair would be a control that is half-forgotten by default.

## The Ceiling Is Race-Free Because It Is One Statement

```sql
UPDATE ai_budgets
SET spent_usd = spent_usd + :amount
WHERE id = :id
  AND breaker_tripped_at IS NULL
  AND spent_usd + :amount <= limit_usd
```

Compare and increment together, so PostgreSQL's row lock serialises concurrent callers and `rowcount` is the answer. The alternative — SELECT the total, add in Python, UPDATE — is a textbook **time-of-check-to-time-of-use race**: two workers both read a total under the ceiling, both proceed, and the ceiling is breached by exactly the amount that makes it not a ceiling.

**Proven, not asserted.** Twenty concurrent threads reserving $1 against a $10 ceiling: exactly ten succeeded, and the running total landed on `10.000000` precisely.

Rows are locked `ORDER BY id`, so two concurrent calls take the same locks in the same order and queue rather than deadlock. Without a deterministic order, one call taking the workspace budget while another takes the workflow budget is a classic deadlock that would surface as an intermittent 500 on a busy workspace.

**All-or-nothing across both ceilings.** A reservation refused by the workflow budget rolls back the workspace budget it already took — otherwise a workspace repeatedly refused by a tight workflow cap would still bleed its workspace cap dry on calls that never happened.

## Two Ceilings, Applied as a Conjunction

| Scope | `workflow_type` | Typical use |
|---|---|---|
| Workspace-wide | `NULL` | the bill |
| One workflow type | e.g. `"chat"` | the runaway detector |

A call must pass **both**, so neither can be used to escape the other. Modelling them in one table rather than two keeps the check a single query.

Budgets are **per period**, not lifetime: `period_started_at + period_interval`. Without that, a ceiling is a cap every workspace eventually hits and never recovers from. The reset advances to `now()` rather than by one interval, so a workspace dormant for several periods starts fresh on first use rather than being reset repeatedly.

> [!note] A period reset deliberately does not clear a tripped breaker
> A breaker that cleared itself when a billing period rolled over would let a runaway resume on a schedule. Resetting one is a decision someone makes.

## Three Tables, Three Questions

| Table | Question | Written | RLS writes |
|---|---|---|---|
| `ai_spend_records` | *What did we spend, on what?* | once per call | **none** — no INSERT or UPDATE policy |
| `ai_budgets` | *May we spend more?* | every call | `owner`/`admin` |
| `ai_shutdown_switches` | *Is spending disabled?* | rarely | `owner`/`admin`, workspace scope only |

**The ledger is append-only from every client path.** Same reasoning as [[Table - audit_log]]: a client able to write its own spend records could forge them — and worse than forging a charge, it could **flood the ledger to poison its own anomaly baseline**, making a real runaway look ordinary. `authenticated` holds `SELECT` and nothing else.

Full schema detail: [[Table - ai_spend_records]] · [[Table - ai_budgets]] · [[Table - ai_shutdown_switches]].

## The Spend Breaker Is Not the Availability Breaker

Two circuit breakers exist and they are deliberately different mechanisms:

| | `ProviderHealthTracker` (STEP-17) | Spend breaker (STEP-18) |
|---|---|---|
| Trips on | consecutive failures | anomalous cost |
| Effect | provider leaves rotation | **the call stops** |
| Recovery | automatic, after 30s | **manual** |
| Lives in | process memory | the database |

**Tripping on cost must stop the call, not route it elsewhere.** A spend breaker that fell back to another provider would spend the *other* provider's budget on a call that was already denied — which is not a spend control at all. `test_the_spend_breaker_does_not_fall_back_to_another_provider` asserts both providers stayed at zero calls.

Recovery is manual because the two failures differ in kind: a provider outage ends on its own, while "something spent more than expected" does not resolve by waiting.

## Governance Errors Sit Outside Both Router Branches

```
ProviderError
├── RetryableProviderError    → retry, then fall back
├── TerminalProviderError     → do not retry; still fall back
└── GovernanceError           → STOP. Neither.
    ├── BudgetExceededError
    ├── SpendBreakerOpenError
    ├── AIShutdownError
    └── ExecutionLimitExceededError
```

Deliberately neither branch. The router acts on those two, so a governance refusal classified as either would be **retried three times or fallen back to another provider** — spending money on a call that was already refused. Guarded by `test_a_spend_refusal_is_not_a_provider_error_the_router_would_retry`.

## Execution Limits Are Not Spend Limits

STEP-17's two ceilings bound one `complete()` at six upstream calls. They say nothing about a workflow that calls `complete()` a hundred times.

`ExecutionBudget` adds three bounds on **one run**, and each catches a runaway shape the others do not:

| Limit | Default | Catches |
|---|---|---|
| `max_invocations` | **5** | an agent re-triggering itself |
| `max_seconds` | 300 | a run that never finishes |
| `max_tokens` | 500,000 | few calls, each enormous |

Five is low deliberately — [[CLAUDE|CLAUDE.md]] §15a asks for an "explicit, low, hard-coded cap", and a legitimate generate → critique → regenerate → verify chain fits inside it while a loop does not.

**A failed call still counts.** Otherwise a workflow retries indefinitely at its own level while the router's ceiling only ever sees single calls.

**One budget per run, passed to every call in it.** That shared tally is what makes the recursion cap real; a fresh budget per call would bound nothing. A standalone call gets a fresh budget rather than none, so every path has a budget to check instead of a branch that skips the check.

Monotonic clock, so an NTP correction mid-run cannot extend or collapse the limit.

### The workflow engine is the first real consumer

[[STEP-22 Minimum Workflow Engine]] is where "one run" stops being hypothetical. `WorkflowRunner` builds **one `ExecutionBudget` per execution** and passes it through `StepContext` to every step, which hands it to `AIService.complete`. `test_every_step_in_one_execution_shares_one_budget` asserts this **by identity** rather than equality — a copy would tally separately and look correct while being just as unbounded.

Two decisions worth recording:

- **A resumed run gets a fresh budget.** The ceiling bounds one *execution*, not the run's whole lifetime: a run paused overnight for approval must not fail on wall-clock time that elapsed while a human was deciding.
- **A tripped ceiling fails the run**, and its public message reaches the run row, so a user seeing a stopped run learns a limit stopped it. §15a's "fails loudly rather than silently continuing", enforced end to end.

See [[Workflow Execution#Governance]].

## Pricing Is Separate From Selection, On Purpose

`AIProvider.cost_per_1k_tokens` is a **selection heuristic**, not billing input, and using it for spend would be wrong three ways: it does not separate prompt from completion rates (which differ 3–5×), it is per provider rather than per model, and it is deliberately approximate — selection needs the *ordering* right, a ceiling needs the *number* right.

`app/ai/pricing.py` holds real rates, as `Decimal`. Never float: money in binary floating point accumulates error, and a ceiling compared against a drifting total is a ceiling that drifts. The database columns are `numeric(12,6)` for the same reason.

> [!danger] An unknown model is charged, never waived
> The most dangerous behaviour this module could have is returning zero for a model it does not recognise — a new model would be **free, uncapped and invisible to every ceiling**, arriving exactly when someone edits a default model name.
>
> `UNKNOWN_MODEL_RATE` is higher than every real rate in the table. A workspace hits its ceiling early and someone investigates; the failure mode is a support ticket rather than a bill. Logged at warning so an operator learns the table needs updating rather than inferring it from a billing discrepancy weeks later.

Rates are hardcoded rather than fetched. A pricing API call on the spend path would make every AI request depend on a second upstream service, and a *failed* lookup would leave a call with no cost to charge against — a budget hole rather than a degraded feature. The honest cost: **when a provider changes prices, this table is wrong until someone updates it.**

## Anomaly Detection Has Teeth

Recent spend (1 hour) against the workspace's **own** baseline (7 days, excluding that hour). Per workspace, never a platform average — a large customer's ordinary hour is a small customer's emergency.

Two thresholds, both deliberately loose:

- **10× the hourly baseline.** This alerts on real customer behaviour, and a tight threshold produces alerts nobody reads — indistinguishable from no alerting.
- **A $1/hour floor.** Without it, a workspace whose baseline is a fraction of a cent trips on its second call. Ten times almost nothing is almost nothing.

A workspace with **no** baseline is not anomalous. A first serious day of use is notable but is not a *deviation*, and treating it as one would trip the breaker on every growing workspace.

When the deviation is extreme this does not merely log — **it trips the spend breaker**, stopping subsequent calls. §15a is explicit that this is an observability requirement, not an optional dashboard.

## Emergency Shutdown, Without a Deploy

Three scopes, all read on every call:

| `workspace_id` | `workflow_type` | Scope |
|---|---|---|
| `NULL` | `NULL` | **the whole platform** |
| `NULL` | set | one workflow, everywhere |
| set | either | one workspace |

**Why a table and not an environment variable.** §15a requires disabling AI spend without a code deploy. Changing an environment variable requires restarting every worker — a deploy in all but name, and precisely the wrong operation during a cost incident. A row is read on the next call, in every worker, with no restart. Demonstrated by `test_shutdown_takes_effect_without_a_restart`: the same service object serves a call, is shut down, and refuses.

> [!warning] The platform switch belongs to no tenant
> `workspace_id IS NULL` matches no RLS policy, so the platform row is invisible to every tenant and creatable by none. Both halves matter: a tenant that could **read** it would learn about an incident affecting other customers, and a tenant that could **write** it could disable AI for every customer on the platform.
>
> The refusal message deliberately does not distinguish a platform shutdown from a workspace one, for the same reason.

## One Connection Per Governed Call

> [!note] A defect found by running it, not by reviewing it
> The repository originally opened a connection per method, so one governed call cost **six** — against a Supabase session pooler limited to 15. Two concurrent calls would exhaust the pool and the third would fail to connect at all, turning a cost control into an availability failure. Observed as `EMAXCONNSESSION` from the pooler during validation.
>
> `AISpendRepository.session()` collapses them to **one**, measured rather than reasoned about (6 → 1). Outside a session each method still opens its own connection, so no method depends on one being open. Guarded by `test_a_guarded_call_uses_a_single_connection`.

## Which Connection, and Why

Unlike every other repository, this one uses **both**, and the choice is a security decision:

| Operation | Connection | Why |
|---|---|---|
| Budget enforcement | privileged | a ceiling must be found whether or not the caller could see it |
| Reserve / settle | privileged | `spent_usd` must not be tenant-writable |
| Ledger write | privileged | a client-writable ledger is a forgeable one |
| Platform switch read | privileged | the row belongs to no tenant |
| A workspace's own spend / budgets | **tenant** | ordinary tenant data, RLS applies |

Over the tenant connection, a row hidden by RLS and a row that does not exist are indistinguishable — the property that makes RLS safe for reads and **wrong for a control**: *"I cannot see a budget"* would become *"there is no budget"*, and no budget means no ceiling.

The tenant boundary is not lost: every privileged method takes the workspace id from the verified request context and filters on it explicitly. What changes is that the filter is this code's responsibility rather than the database's.

## No Bypass

**`AIService.complete()` is the single choke point**, and `AIRouter` is deliberately not exposed as its own route-level dependency. A second path from a route to the router would spend money without passing a single §15a control — and would look perfectly ordinary at the call site.

Three things enforce it rather than one convention:

- `AISpendService` is a **required** constructor argument on `AIService`. A permissive default would mean forgetting to wire governance still worked — by spending without a ceiling.
- `test_no_route_can_reach_the_router_without_the_ai_service` inspects the wiring module and asserts `AIRouterDep` is consumed exactly once.
- `test_every_governance_refusal_happens_before_the_provider_call` asserts zero provider calls across every refusal.

## Known Limitations

Stated so the next reader does not assume otherwise:

- ~~**An owner can currently zero their own `spent_usd`.**~~ **Closed by [[STEP-19 Settings and BYOK UI]].** Migration `c9d3b71e08af` revokes the table-wide `UPDATE` on `ai_budgets` and grants `UPDATE (limit_usd, period_interval)` instead, so the running total is unwritable over the request connection regardless of what any route accepts — the column-level mechanism RLS structurally cannot provide. Verified live, with a negative control re-granting the column to observe the breach before revoking it again. See [[Table - ai_budgets]].
- **No budget is configured by default**, so a new workspace is unmetered rather than blocked. Refusing every call on a platform that has not asked anyone to set a limit would be the wrong default; whether it stays that way in production is a launch decision ([[STEP-25 Launch Readiness Criteria]]).
- **Anomaly detection runs inline**, after each recorded call. It is near-real-time as §15a requires, but it adds two queries to the settle path. A background evaluation is the natural evolution once there is a scheduler.
- **Prompt token estimation is `len // 4`**, not a real tokenizer. It feeds only the pre-call reservation and is replaced by the provider's real count on settlement. A real tokenizer means a dependency per provider ([[CLAUDE|CLAUDE.md]] §28) to compute a number discarded moments later.
- ~~**No HTTP routes.**~~ **[[STEP-19 Settings and BYOK UI]] added them:** `GET`/`PUT .../ai/budgets` and `GET .../ai/spend`, members reading and owners/admins writing, with governance refusals surfacing as 402 or 503 — see [[API Endpoints#AI settings — providers, budgets and spend]]. A budget can now be configured and a refusal understood without a database client.
- **Budget periods are configured, not the breaker.** A tripped spend breaker is deliberately **not** resettable from the settings surface: it trips because something spent more than expected, which does not resolve by the tenant clearing it. Resetting is a manual decision (`AISpendRepository.reset_breaker`), and the request schema is not a path to it.
- **Alerting is a log line at `ERROR`**, not a pager. Routing it to an on-call channel is infrastructure ([[Infrastructure]]), not application code.

---

## Navigation

- **Previous:** [[AI Router Implementation]]
- **Next:** [[Web Session Handling]]
- **Parent:** [[Architecture MOC]]
- **Related Notes:** [[AI Router Implementation]] · [[AI Providers]] · [[RLS Policy Pattern]] · [[Table - ai_spend_records]] · [[Table - ai_budgets]] · [[Table - ai_shutdown_switches]] · [[Security Architecture]]
