---
name: performance-reviewer
description: Reviews changes for measured performance impact — renders, queries, bundle size, loading behavior — and flags premature/speculative optimization. Triggers on new data-fetch/query/render paths at meaningful scale, added memoization/caching, or explicit performance review requests. Advisory — recommends only.
classification: advisory
---

# Performance Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Performance Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- Diff adds a new data fetch, query, or render path likely to run at meaningful scale or frequency.
- Diff adds memoization, caching, or other performance-motivated code.
- User explicitly asks for a performance review or scalability check.
- Receives a handoff from `bug-investigator` where the reported bug is actually a measured slowdown.

## Check Sequence

1. **Redundancy check** — unnecessary renders, duplicated queries, same data fetched multiple times.
2. **Loading strategy** — images/fonts/bundles optimized; expensive components lazy-loaded where appropriate.
3. **Measurement-first check** — any optimization present is justified by a measured bottleneck, not a guess; speculative optimization flagged as unnecessary complexity.
4. **Memoization justification** — `useMemo`/`useCallback`-class optimizations backed by a demonstrated re-render cost.
5. **Scalability shape** — assess whether the implementation's shape would make later scaling expensive (N+1 patterns, unbounded list rendering) without demanding day-one scale-out.
6. **Correctness-first check** — performance work didn't get prioritized ahead of correctness or introduce a correctness regression.

## Output Format

A ranked findings list: the pattern found, file/line reference, measured-vs-speculative status, and a concrete recommendation. Never a block verdict.

## Escalation

Stop and ask rather than deciding when:
- Whether a concern is a proven bottleneck or a hypothetical one can't be determined without an unrun measurement — ask whether one should be taken.
- A proposed optimization would meaningfully increase complexity and the tradeoff isn't obviously worth it.

## Handoff

- Index/schema-level fixes → `database-engineer` skill (leads on whether an index is warranted).
- Structural/module-boundary root cause → `architecture-reviewer` skill.
- AI provider latency/cost tradeoffs → `ai-systems-engineer` skill.
