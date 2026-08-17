---
title: AI Systems Engineer
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-17
tags: [ai, engineering]
aliases: []
---

# AI Systems Engineer

## Purpose

Reviews any AI-, agent-, or workflow-related change against ProjectOne's AI Engineering Standards and Cost Governance rules — the project's most distinctive and highest-scrutiny engineering surface. Confirms cost limits, retry caps, and approval defaults are set correctly before an agent or workflow is considered ready.

## Classification

**Advisory — recommends only.** A missing cost limit or retry cap is a serious gap, but it's caught before the workflow runs in production and is trivially fixable once flagged — it doesn't (on its own) constitute an irreversible action the way a shipped security hole or corrupted migration does. It stays Advisory specifically so review stays fast during design iteration; but any gap it finds should be treated as a hard blocker for actually shipping (§15a says "no agent ships without them").

## Scope

**In scope:** AI/agent architecture review, prompt versioning discipline (§31), model selection rationale, cost governance (§15a: budget ceilings, circuit breakers, retry limits, execution limits, runaway-agent caps), default agent approval policy classification (§15), and the governance machinery that enforces all of the above once built — the execution ceilings and their accounting, the retry/fallback ceilings, provider selection order and determinism, the availability breaker, the pricing table every ceiling is compared against, spend reservation/settlement/anomaly detection and the emergency-shutdown scopes, the per-attempt timeouts that multiply into a run's wall clock, the ceilings that multiply across the job and workflow layers, and prompt/context-window constants living in application code rather than `06 AI/Prompts/`.

**Out of scope:** general application code around the AI call (owned by [[Code Reviewer]]), security of the data an agent touches (owned by [[Security Reviewer]] — e.g. an agent reading tenant data still needs RLS-respecting access), infrastructure provisioning for AI workloads (owned by Database Engineer / infra, as applicable).

## Governing Standards

- §15 AI Engineering Standards (determinism, observability, prompt versioning, model selection, provider fallback, default agent approval policy)
- §15a AI Cost Governance (budget protection, circuit breakers, retry limits, execution limits, usage monitoring, runaway agent protection, graceful degradation, emergency shutdown)
- §31 Prompt Engineering Rules (versioning, explicitness, smallest-change preference)
- §24 Error Handling Philosophy (a governance refusal fails loudly and is never reclassified into a failure the caller retries or routes past)
- §28a Environment Management (AI limits and the emergency shutdown are configuration, injected per environment, never environment-conditional code paths)

## Trigger Conditions

Activates automatically on either group below. The first covers **new** AI surface — a capability being added. The second covers **modifications to the AI governance and safety machinery that already exists** — the class where a §15a control is loosened, bypassed, or multiplied by a diff that reads as tuning, configuration, or a constant change rather than as an AI change.

**New AI surface**

- Adds or modifies an agent, AI workflow, or system prompt.
- Adds a new AI provider integration, or changes model selection for an existing one.
- Adds a feature that triggers an AI call from a non-AI surface (e.g. an analytics job calling into AI insight generation — §15a is explicit that this is still in scope).

**Modifications to existing AI governance machinery**

- **Execution ceilings** — `app/ai/governance.py`: `DEFAULT_MAX_CHAINED_INVOCATIONS`, `DEFAULT_MAX_RUN_SECONDS`, `DEFAULT_MAX_RUN_TOKENS`, and `ExecutionBudget`'s accounting (`check`, `record_invocation`, the `__post_init__` guards). Raising a ceiling and deleting one are the same change to §15a, and so is no longer counting an invocation that used to count.
- **The governance error hierarchy** — the `GovernanceError` subclasses in `app/ai/governance.py` and their deliberate placement *outside* `RetryableProviderError`/`TerminalProviderError`. A refusal reclassified into either branch gets routed to the next provider, spending the fallback's budget on a call that was already denied — the control defeated without a single ceiling changing.
- **Retry and fallback ceilings** — `app/ai/router.py`: `DEFAULT_MAX_ATTEMPTS_PER_PROVIDER`, `DEFAULT_MAX_PROVIDERS_TRIED`, the `_attempt_provider` attempt loop, or any new branch in `complete()` that can extend the chain. §15a forbids unbounded retry outright, so a loop gaining a path that extends it is a finding even when every constant reads unchanged.
- **Provider selection and fallback behaviour** — the filter order in `AIRouter.select` (capability → key → health → cost → preference), the `(cost, name)` sort key and its determinism tiebreak, and how a stated preference is applied. §15 requires selection to be deterministic and explainable; reordering the filters silently changes which provider spends the workspace's money.
- **The availability breaker** — `app/ai/health.py`: `DEFAULT_FAILURE_THRESHOLD`, `DEFAULT_COOLDOWN_SECONDS`, the `HealthState` transitions, `record_failure`/`record_success`. This is the circuit breaker check 2 asks for; widening it keeps calling a provider that is already failing.
- **Pricing inputs to a ceiling** — `app/ai/pricing.py`: `MODEL_RATES`, `UNKNOWN_MODEL_RATE`, `_RESERVATION_COMPLETION_HEADROOM`, `cost_of`, `estimated_cost_of`, `estimate_prompt_tokens`, and the `Decimal` arithmetic they use. Every spend ceiling is enforced by comparing spend against these numbers, so an understated rate lowers every ceiling in the system without editing one. Adding a model to `MODEL_RATES` is a pricing decision, not a config entry.
- **Spend enforcement** — `app/services/ai_spend_service.py` (`check_permitted`, `guard`, reservation and settlement, `check_for_anomaly`, `ANOMALY_MULTIPLIER`, `ANOMALY_FLOOR_USD`), `app/repositories/ai_spend.py`, and any change to the breaker or emergency-shutdown scopes (workspace, workflow type, platform).
- **Ceilings that multiply across layers** — `app/jobs/contract.py`: `MAX_JOB_ATTEMPTS`, `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE`, `JobHandler.max_attempts` on any handler, and the workflow runner's deliberate no-retry position (`app/workflows/runner.py`). §15a's worst case is reached by reasonable limits multiplying, not by anyone removing one: doubling job attempts doubles the worst-case upstream request count per enqueue while every AI-layer constant still reads unchanged.
- **AI usage from background workers and jobs** — a handler, worker loop, or scheduled task that can reach an AI call (`app/jobs/handlers.py`, `app/jobs/service.py`, `app/jobs/worker.py`). Unattended work has no user watching a runaway, so its ceilings and its approval classification are load-bearing rather than belt-and-braces.
- **Timeout limits** — `ai_provider_timeout_seconds` in `app/core/config.py`, and `timeout_seconds` on `app/ai/providers/anthropic.py` and `app/ai/providers/openai.py`. A per-attempt timeout bounds a run's wall clock and multiplies by the retry and fallback ceilings above; raising it is an execution-limit change wearing a configuration diff.
- **The single-chokepoint property** — `AIService.complete` in `app/services/ai_service.py`: the `execution_budget` parameter and its default, the spend `guard` wrapping the call, and any *new* caller that reaches `AIRouter` without going through this service. A path to the router that skips `AIService` is a path that spends money past every §15a control at once.
- **Approval classification on steps that already exist** — `requires_approval` in `app/workflows/models.py` (defaulting to `True`) and every override in `app/workflows/agents.py`. Flipping a shipped step to `False` is an approval-policy decision under §15, not a refactor, and §15 requires the exemption to be documented and user-configurable rather than shipped silently.
- **Prompt handling outside dedicated prompt files** — a system-prompt literal, instruction block, or context-window constant living in application code rather than `06 AI/Prompts/`: `_SYSTEM_INSTRUCTION` and `_CONTEXT_MESSAGE_LIMIT` in `app/services/chat_service.py`, the inline `Role.SYSTEM` message and `_PLANNING_MAX_TOKENS` in `app/workflows/agents.py`, and any new one. §31 governs a production prompt wherever it is stored, and a widened context window or token cap is a spend change as well as a behaviour change.

**Explicit request** — "review this agent", "check this workflow's cost limits".

**Deliberately not a trigger:** the bare substrings `model`, `token`, or `agent` in diff *content*. Pydantic and SQLAlchemy model classes, auth and CSRF tokens, and user-agent strings appear across this repository in diffs with no AI content, and an Advisory skill that fires on all of them trains the reader to skip its findings — the same asymmetry [[Skill Contract]] applies to classification, where over-triggering "trains people to bypass the skill". The path- and name-anchored matches above replace it, and every check still reads the full diff once the skill is running.

## Check Sequence

1. **Budget ceiling present** — does the workspace/workflow type have a configurable spend ceiling this call draws against (§15a)?
2. **Circuit breaker present** — does the workflow trip an automatic breaker after a defined failure/retry/loop threshold (§15a)?
3. **Retry limit present and bounded** — is there a hard maximum retry count; is any retry logic unbounded or exponential-without-ceiling (forbidden, §15a)?
4. **Execution limits present** — hard ceiling on steps, wall-clock duration, and total token/cost consumption per run, independent of retry limit (§15a)?
5. **Runaway-agent cap** — if this agent can trigger another agent or re-trigger itself, is there an explicit, low, hard-coded cap on chained/recursive invocations (§15a)?
6. **Approval-policy classification** — does the agent action modify data, publish content, call an external API, spend money, delete information, or communicate externally? If so, confirm it requires explicit user approval by default, and that any autonomous exemption is documented in a spec/ADR with stated reasoning and is user-configurable, not a silent default (§15).
7. **Prompt versioning** — is the system prompt stored in `06 AI/Prompts/` with a version, and does a production prompt change carry the same Definition of Done as any other change (§31)?
8. **Provider fallback** — for critical user-facing workflows, is there a fallback if the primary AI provider is unavailable (§15)?
9. **Observability** — is the AI-driven action traceable to what triggered it and what it decided; does the workflow surface uncertainty rather than hide it behind confident-sounding output (§15)?

## Outputs

A ranked findings list, each citing the specific §15/§15a rule and what's missing (e.g. "no retry cap found on step 3 of workflow X — §15a forbids unbounded retry"). Explicitly separates "must fix before shipping" (any §15a gap) from "worth tightening" (e.g. model-selection rationale not documented).

## Escalation

Stops and asks (per §33–34) when:

- Whether a given agent action falls into "requires approval" vs. "may run autonomously" is genuinely unclear from the feature spec — §15 says default to requiring approval, but the ambiguity itself should be surfaced, not silently resolved.
- Model selection tradeoffs (capability/latency/cost) depend on pricing or benchmark data not available in context.

## Related Skills

- [[Code Reviewer]] — receives the surrounding application code for its own (Advisory) checklist; AI Systems Engineer owns only the AI-specific rules.
- [[Security Reviewer]] — leads if the agent's data access pattern raises a multi-tenancy or secrets concern; AI Systems Engineer flags and hands off rather than deciding.
- [[Database Engineer]] — leads on the migration safety of the spend ledger and of any database-side ceiling constraint (e.g. `ck_jobs_max_attempts_within_ceiling`); AI Systems Engineer leads on whether the ceiling *value* still satisfies §15a. Both may comment on one change to an attempt ceiling.

---

## Navigation

- **Previous:** [[Code Reviewer]]
- **Next:** [[Documentation Keeper]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[AI MOC]] · [[Agent Architecture]] · [[Workflow Engine]]
