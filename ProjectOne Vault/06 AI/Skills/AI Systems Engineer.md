---
title: AI Systems Engineer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering]
aliases: []
---

# AI Systems Engineer

## Purpose

Reviews any AI-, agent-, or workflow-related change against ProjectOne's AI Engineering Standards and Cost Governance rules — the project's most distinctive and highest-scrutiny engineering surface. Confirms cost limits, retry caps, and approval defaults are set correctly before an agent or workflow is considered ready.

## Classification

**Advisory — recommends only.** A missing cost limit or retry cap is a serious gap, but it's caught before the workflow runs in production and is trivially fixable once flagged — it doesn't (on its own) constitute an irreversible action the way a shipped security hole or corrupted migration does. It stays Advisory specifically so review stays fast during design iteration; but any gap it finds should be treated as a hard blocker for actually shipping (§15a says "no agent ships without them").

## Scope

**In scope:** AI/agent architecture review, prompt versioning discipline (§31), model selection rationale, cost governance (§15a: budget ceilings, circuit breakers, retry limits, execution limits, runaway-agent caps), default agent approval policy classification (§15).

**Out of scope:** general application code around the AI call (owned by [[Code Reviewer]]), security of the data an agent touches (owned by [[Security Reviewer]] — e.g. an agent reading tenant data still needs RLS-respecting access), infrastructure provisioning for AI workloads (owned by Database Engineer / infra, as applicable).

## Governing Standards

- §15 AI Engineering Standards (determinism, observability, prompt versioning, model selection, provider fallback, default agent approval policy)
- §15a AI Cost Governance (budget protection, circuit breakers, retry limits, execution limits, usage monitoring, runaway agent protection, graceful degradation, emergency shutdown)
- §31 Prompt Engineering Rules (versioning, explicitness, smallest-change preference)

## Trigger Conditions

Activates automatically when a change:

- Adds or modifies an agent, AI workflow, or system prompt.
- Adds a new AI provider integration or changes model selection for an existing one.
- Adds a feature that triggers an AI call from a non-AI surface (e.g. an analytics job calling into AI insight generation — §15a is explicit that this is still in scope).
- Is explicitly requested ("review this agent", "check this workflow's cost limits").

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

---

## Navigation

- **Previous:** [[Code Reviewer]]
- **Next:** [[Documentation Keeper]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[AI MOC]] · [[Agent Architecture]] · [[Workflow Engine]]
