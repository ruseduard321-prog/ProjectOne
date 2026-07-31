---
title: Performance Reviewer
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering]
aliases: []
---

# Performance Reviewer

## Purpose

Reviews changes for measured (not guessed) performance impact — renders, queries, bundle size, load behavior — and confirms optimization work is justified by an actual bottleneck rather than intuition. Also confirms new code doesn't introduce an obvious, foreseeable performance regression before it ships.

## Classification

**Advisory — recommends only.** §17 itself frames performance as something to measure and improve incrementally, correctness-first; a performance gap is real but essentially never irreversible — it's discovered, measured, and fixed in a normal iteration cycle, unlike a Critical skill's failure modes.

## Scope

**In scope:** unnecessary renders/queries/duplicated requests, loading strategy (images, fonts, bundles, lazy-loading), premature-optimization detection (flagging speculative work not backed by measurement), scalability shape of a first implementation (§17's "the shape of the first implementation determines how expensive it is to add scale later").

**Out of scope:** whether an index is speculative (owned by [[Database Engineer]] — Performance Reviewer can recommend investigating a query, but index-addition discipline is Database Engineer's check), AI provider latency/cost tradeoffs (owned by [[AI Systems Engineer]]), general code quality unrelated to performance (owned by [[Code Reviewer]]), structural/architectural performance characteristics that stem from a module boundary decision (owned by [[Architecture Reviewer]] for the boundary itself; Performance Reviewer measures the resulting runtime behavior).

## Governing Standards

- §17 Performance Standards (avoid unnecessary renders/queries/duplication, optimize loading, measure before optimizing, correctness precedes performance, design for scalability without premature optimization)
- §11 Frontend Standards (memoize only when profiling shows measurable benefit — this is Performance Reviewer's main frontend-specific check)

## Trigger Conditions

Activates automatically when a change:

- Adds a new data fetch, query, or render path likely to run at meaningful scale or frequency.
- Adds memoization, caching, or other performance-motivated code.
- Is explicitly requested ("review performance", "is this going to scale", "check for unnecessary re-renders").
- Follows a [[Bug Investigator]] handoff where the reported "bug" is actually a measured slowdown.

## Check Sequence

1. **Redundancy check** — look for unnecessary renders, duplicated queries, or the same data fetched multiple times across a feature (§17, §11 anti-patterns).
2. **Loading strategy** — images, fonts, and bundles optimized; expensive components lazy-loaded where appropriate (§17).
3. **Measurement-first check** — confirm any optimization present is justified by an actual measured bottleneck, not a guess; flag speculative optimization as unnecessary complexity (§17, §29 — premature optimization is itself a smell here).
4. **Memoization justification** — confirm `useMemo`/`useCallback`-class optimizations are backed by a demonstrated re-render cost, not applied reflexively (§11).
5. **Scalability shape** — assess whether the first implementation's shape would make later scaling expensive (e.g. N+1 query patterns, unbounded list rendering) without demanding day-one scale-out (§17).
6. **Correctness-first check** — confirm performance work didn't get prioritized ahead of correctness or introduce a correctness regression in pursuit of speed (§17, §5).

## Outputs

A ranked findings list: the specific pattern found, file/line reference, whether it's a measured problem or a speculative one, and a concrete recommendation (e.g. "this optimization has no attached measurement — either attach a profile or remove it," "this fetch runs once per list item — batch it"). Never a block verdict.

## Escalation

Stops and asks (per §33–34) when:

- Whether a performance concern is actually a proven bottleneck or a hypothetical one can't be determined without a measurement that hasn't been run — asks whether one should be taken rather than guessing at severity.
- A proposed optimization would meaningfully increase complexity and the tradeoff against that complexity isn't obviously worth it (ties to §5's "performance only after correctness" and §29's refactoring discipline).

## Related Skills

- [[Bug Investigator]] — hands off to Performance Reviewer when a reported bug turns out to be a measured regression rather than incorrect behavior.
- [[Database Engineer]] — leads on whether a new index is warranted; Performance Reviewer can recommend investigating a slow query but doesn't approve schema-level fixes itself.
- [[Architecture Reviewer]] — owns whether a structural/module-boundary decision is sound; Performance Reviewer measures the runtime consequences of that decision.
- [[AI Systems Engineer]] — leads on AI provider latency/cost tradeoffs specifically.

---

## Navigation

- **Previous:** [[Bug Investigator]]
- **Next:** [[Release Manager]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Skill Contract]]
