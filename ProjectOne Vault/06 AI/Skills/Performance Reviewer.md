---
title: Performance Reviewer
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-18
tags: [ai, engineering]
aliases: []
---

# Performance Reviewer

## Purpose

Reviews changes for measured (not guessed) performance impact — renders, queries, bundle size, load behavior — and confirms optimization work is justified by an actual bottleneck rather than intuition. Also confirms new code doesn't introduce an obvious, foreseeable performance regression before it ships. A shipped path is covered the same way as a new one: modifying or deleting an existing optimization, bound, parallel structure, loading strategy, or pacing mechanism is as performance-significant as adding one.

## Classification

**Advisory — recommends only.** §17 itself frames performance as something to measure and improve incrementally, correctness-first; a performance gap is real but essentially never irreversible — it's discovered, measured, and fixed in a normal iteration cycle, unlike a Critical skill's failure modes. Advisory also bounds what a clean result means: a Performance Reviewer PASS is input, never a substitute for [[Code Reviewer]]'s finished-diff review, [[Database Engineer]]'s or [[AI Systems Engineer]]'s lead checks, or a §21 owner gate.

## Scope

**In scope:** unnecessary renders/queries/duplicated requests, loading strategy (images, fonts, bundles, lazy-loading — added, changed, or removed), premature-optimization detection (flagging speculative work not backed by measurement), scalability shape of a first implementation (§17's "the shape of the first implementation determines how expensive it is to add scale later"), the runtime consequences of modifying or removing an existing optimization or bound, backend query and result-set behavior (repository and service query shapes, bounded versus unbounded listings), cache invalidation and revalidation scope, background execution cadence (worker polling, job-claim volume, heartbeat and retry pacing — their latency, throughput, and platform-load consequences), and performance evidence (benchmarks, load tests, budgets, thresholds, and the quality bar they enforce).

**Out of scope:** whether an index is speculative (owned by [[Database Engineer]] — Performance Reviewer can recommend investigating a query, but index-addition discipline is Database Engineer's check), AI provider latency/cost tradeoffs, AI retry ceilings, spend limits and provider constraints (owned by [[AI Systems Engineer]] under §15a), general code quality unrelated to performance (owned by [[Code Reviewer]], including retry correctness beyond the load questions in check 7), structural/architectural performance characteristics that stem from a module boundary decision (owned by [[Architecture Reviewer]] for the boundary itself; Performance Reviewer measures the resulting runtime behavior), and implementing the feature or the fix (owned by [[Full Stack Engineer]] — Performance Reviewer evaluates consequences and recommends; it never becomes the implementation owner).

## Governing Standards

- §17 Performance Standards (avoid unnecessary renders/queries/duplication, optimize loading, measure before optimizing, correctness precedes performance, design for scalability without premature optimization)
- §11 Frontend Standards (memoize only when profiling shows measurable benefit — this is Performance Reviewer's main frontend-specific check)

## Trigger Conditions

Activates on changes to **performance-significant behavior — added, modified, or removed** — in any layer: frontend render, server response, backend query, or background worker. A performance path being *touched* is never sufficient on its own; what fires this skill is a runtime behavior changing.

**Fetch, query and result-set behavior**

- A new data fetch, query, or render path likely to run at meaningful scale or frequency.
- A shipped fetch/query/render path whose runtime behavior changes — what it fetches, how often, or how much.
- A result set widened or unbounded: a `LIMIT` raised or removed, a pagination bound dropped, a filtered listing broadened. The repository layer is deliberately split on this line — the jobs, workflows, conversations and audit listings in `apps/api/app/repositories/` are `LIMIT`-bounded, while the users and projects listings are deliberately unbounded because RLS and workspace size make that safe today — so deleting one of those bounds, or adding a new unbounded listing over a table that grows per use, is exactly the change this trigger exists for.

**Optimization, bound or parallelism removed**

- An existing optimization deleted or weakened: memoization, caching, lazy-loading, batching, a query bound, or a parallel fetch structure. Removing an optimization is as performance-significant as adding one, and needs either a measurement showing it was unnecessary or a correctness reason, stated in the change.
- Parallel work serialized: the `Promise.all` fan-outs in the shipped dashboard and settings pages becoming sequential awaits would add whole round-trips of latency while adding no "new path" anywhere.

**Caching, memoization and invalidation behavior**

- Memoization, caching, or other performance-motivated code added — the measurement-first check exists for exactly this, including speculative optimization the diff introduces.
- Cache invalidation or revalidation scope changed: the `revalidatePath` call sites in the settings and chat server actions each invalidate one route; widening one to a layout, dropping one, or adding a broader invalidation changes how much work every subsequent request repeats.

**Loading and bundle behavior**

- A lazy-loading or dynamic-import boundary added, changed, weakened, or removed.
- Image, font, or bundle loading behavior changed, or client bundle composition materially widened — a Server Component becoming a Client Component pulls its subtree into the client bundle, so the §11 boundary decision is [[Full Stack Engineer]]'s while the resulting load-time cost is this skill's.
- A shipped loading strategy changed in a way that alters the work performed at load time. A path or asset merely being touched is not enough — the runtime loading behavior must change materially.

**Background execution cadence**

- Worker polling, job-claim, heartbeat, or retry pacing changed: the poll interval and idle-wait rule in `apps/api/app/jobs/worker.py`, the lease-fraction heartbeat interval, the claim volume of the `FOR UPDATE SKIP LOCKED ... LIMIT` query in `apps/api/app/repositories/job_dispatch.py`, and the pacing defaults in `apps/api/app/core/config.py`. Cadence multiplies: a shorter interval or a larger claim batch is a platform-wide load change, not a local edit.
- A new scheduled, background, or looping execution path — anything that runs unattended on a cadence rather than per request. ([[Architecture Reviewer]] owns whether the execution substrate itself is permitted; this skill evaluates its cadence and runtime load shape. Both may fire on one change.)
- Where a cadence or pacing change materially changes AI-call frequency or spend, [[AI Systems Engineer]] fires independently alongside this skill — it owns retry ceilings, spend limits, and provider constraints (§15a); this skill owns the latency, throughput, and platform-load consequences.

**Performance evidence and thresholds**

- Performance benchmark or load-test evidence added, changed, or removed.
- A performance budget or regression threshold introduced, widened, weakened, skipped, or deleted.
- A performance assertion changed in a way that alters the quality bar the suite enforces. This trigger is about the evidence and the bar, not test mechanics — ordinary test-only changes stay excluded, per the negative clauses below.

**Requests and handoffs**

- Explicitly requested ("review performance", "is this going to scale", "check for unnecessary re-renders").
- A [[Bug Investigator]] handoff where the reported "bug" is actually a measured slowdown — Bug Investigator leads the diagnosis; this skill evaluates the performance shape of the fix.
- A [[Full Stack Engineer]] handoff where implementation work adds, changes, or removes a performance-significant path — see Related Skills for the boundary.

**Not a trigger.**

- A formatting, naming, or documentation-only change to a file containing a performance path — reformatting repository SQL or renaming a fetch helper changes no runtime behavior.
- A change to a query/render path whose runtime behavior is unchanged — a mechanical refactor, a type annotation, a moved file.
- A test-only change that alters no performance evidence or threshold — mocking `revalidatePath` in a test is not a revalidation change.
- The absence of optimization on a path with no meaningful scale and no measured problem — this skill never fires to propose a speculative micro-optimization; that would violate its own measurement-first discipline (§17). A diff that *introduces* speculative optimization still fires — the measurement-first check exists to evaluate it.
- A general feature-behavior change with no performance-significant dimension — owned by [[Full Stack Engineer]] (implementation) and [[Code Reviewer]] (finished diff).

## Check Sequence

1. **Redundancy check** — look for unnecessary renders, duplicated queries, or the same data fetched multiple times across a feature — frontend renders and backend service/repository calls alike (§17, §11 anti-patterns).
2. **Loading strategy** — images, fonts, and bundles optimized; expensive components lazy-loaded where appropriate; and a modified or removed loading strategy evaluated the same way as an added one — a lazy-loading or dynamic-import boundary weakened or dropped, or load-time work widened, is a regression candidate, not a neutral edit (§17).
3. **Measurement-first check** — confirm any optimization present is justified by an actual measured bottleneck, not a guess; flag speculative optimization as unnecessary complexity (§17, §29 — premature optimization is itself a smell here).
4. **Memoization justification** — confirm `useMemo`/`useCallback`-class optimizations are backed by a demonstrated re-render cost, not applied reflexively (§11).
5. **Scalability shape** — assess whether the first implementation's shape would make later scaling expensive (e.g. N+1 query patterns, unbounded list rendering, unbounded repository listings over tables that grow per use) without demanding day-one scale-out (§17).
6. **Regression check** — when a shipped path is modified or something is removed, compare before and after: was parallel work serialized, a bound removed or widened, caching/memoization/lazy-loading deleted, an invalidation widened or dropped? A removed optimization — and a performance benchmark, budget, threshold, or assertion that is weakened, skipped, or deleted — needs an explicit measured justification, not silence (§17).
7. **Cadence check** — for background execution, evaluate the concrete pacing conditions: idle polling cannot degrade into a zero-delay or tight loop; a worker that has just found work proceeds to the next item without an unnecessary fixed idle delay; heartbeat cadence stays safely inside lease expiry; claim batch size, concurrency, and polling frequency are assessed for their combined database/platform load, not one dial at a time; retry/backoff pacing does not multiply unattended work or request volume (§17). Where the cadence drives AI calls, hand the frequency/spend consequence to [[AI Systems Engineer]]; retry correctness beyond these load questions stays with [[Code Reviewer]] on the finished diff.
8. **Correctness-first check** — confirm performance work didn't get prioritized ahead of correctness or introduce a correctness regression in pursuit of speed (§17, §5).

## Outputs

A ranked findings list: the specific pattern found, file/line reference, whether it's a measured problem or a speculative one, and a concrete recommendation (e.g. "this optimization has no attached measurement — either attach a profile or remove it," "this fetch runs once per list item — batch it"). Never a block verdict.

## Escalation

Stops and asks (per §33–34) when:

- Whether a performance concern is actually a proven bottleneck or a hypothetical one can't be determined without a measurement that hasn't been run — asks whether one should be taken rather than guessing at severity.
- A proposed optimization would meaningfully increase complexity and the tradeoff against that complexity isn't obviously worth it (ties to §5's "performance only after correctness" and §29's refactoring discipline).

## Related Skills

- [[Bug Investigator]] — hands off to Performance Reviewer when a reported bug turns out to be a measured regression rather than incorrect behavior.
- [[Database Engineer]] — leads on whether a new index is warranted; Performance Reviewer can recommend investigating a slow query but doesn't approve schema-level fixes itself.
- [[Architecture Reviewer]] — owns whether a structural/module-boundary decision is sound — including whether a new background/scheduled execution substrate is permitted; Performance Reviewer measures the runtime consequences of that decision, and both may fire on one change.
- [[AI Systems Engineer]] — leads on AI provider latency/cost tradeoffs, retry ceilings, spend limits, and provider constraints (§15a). When a cadence or pacing change materially changes AI-call frequency or spend, both skills fire independently — this skill on latency/throughput/platform load, AI Systems Engineer on the AI-cost axis.
- [[Full Stack Engineer]] — owns implementing feature behavior inside the approved architecture, including any accepted performance recommendation; hands off here when that implementation adds, changes, or removes a performance-significant path. Performance Reviewer evaluates consequences and recommends — it never becomes the implementation owner, and both skills firing on one change is the sequence working, not a routing conflict.

---

## Navigation

- **Previous:** [[Bug Investigator]]
- **Next:** [[Release Manager]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Skill Contract]]
