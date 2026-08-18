---
name: performance-reviewer
description: Reviews changes for measured performance impact — renders, queries, result-set bounds, loading and bundle behavior, caching and invalidation, background worker cadence, and performance evidence/thresholds — and flags premature/speculative optimization. Triggers on performance-significant runtime behavior added, modified, or removed — new fetch/query/render paths at meaningful scale; shipped paths whose runtime behavior changes materially; performance-motivated optimization added, including caching or memoization; existing optimization, bound, parallel structure, caching or memoization weakened or removed; widened or unbounded result sets; cache invalidation/revalidation scope changes; lazy-loading, dynamic-import or bundle-loading behavior changes; worker polling, claim, heartbeat or retry pacing changes; new scheduled/background execution; benchmark or load-test evidence added, changed or removed; a performance budget or regression threshold introduced, widened, weakened, skipped or deleted; a performance assertion changed when it alters the enforced quality bar — plus explicit performance requests and bug-investigator or full-stack-engineer handoffs. Not triggered by formatting/naming/doc-only changes, behavior-preserving refactors, or ordinary test-only changes. Advisory — recommends only.
classification: advisory
---

# Performance Reviewer

Source of truth: `ProjectOne Vault/06 AI/Skills/Performance Reviewer.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on **performance-significant behavior — added, modified, or removed**, in any layer (frontend render, server response, backend query, background worker). A performance path being touched is never sufficient on its own.

**Fetch/query/result-set behavior**
- New data fetch, query, or render path likely to run at meaningful scale or frequency.
- Shipped fetch/query/render path whose runtime behavior changes — what it fetches, how often, or how much.
- Result set widened or unbounded: a `LIMIT` raised or removed, a pagination bound dropped, a listing broadened, a new unbounded listing over a table that grows per use (bounded listings in `apps/api/app/repositories/` are the reference shape).

**Optimization/bound/parallelism removed**
- Existing memoization, caching, lazy-loading, batching, query bound, or parallel fetch structure deleted or weakened — needs a stated measurement or correctness reason.
- Parallel work serialized (a `Promise.all` fan-out becoming sequential awaits in a shipped page).

**Caching/invalidation**
- Memoization, caching, or other performance-motivated code added — including speculative optimization the diff introduces.
- Cache invalidation/revalidation scope changed — a `revalidatePath` site widened, dropped, or broadened.

**Loading/bundle behavior**
- Lazy-loading or dynamic-import boundary added, changed, weakened, or removed.
- Image/font/bundle loading behavior changed, or client bundle composition materially widened (e.g. a Server→Client Component conversion pulling a subtree into the client bundle).
- Shipped loading strategy changed in a way that alters work performed at load time. A path or asset being touched is not enough — runtime loading behavior must change materially.

**Background execution cadence**
- Worker polling, job-claim, heartbeat, or retry pacing changed (`apps/api/app/jobs/worker.py`, the claim query in `apps/api/app/repositories/job_dispatch.py`, pacing defaults in `apps/api/app/core/config.py`).
- New scheduled, background, or looping execution path running unattended on a cadence (`architecture-reviewer` owns the substrate; this skill owns cadence and load shape — both may fire).
- Cadence change materially changing AI-call frequency or spend → `ai-systems-engineer` also fires independently.

**Performance evidence and thresholds**
- Performance benchmark or load-test evidence added, changed, or removed.
- Performance budget or regression threshold introduced, widened, weakened, skipped, or deleted.
- Performance assertion changed in a way that alters the quality bar. Ordinary test-only changes stay excluded.

**Requests and handoffs**
- User explicitly asks for a performance review or scalability check.
- Handoff from `bug-investigator` where the reported bug is actually a measured slowdown.
- Handoff from `full-stack-engineer` where implementation adds, changes, or removes a performance-significant path.

**Not a trigger:** formatting, naming, or documentation-only changes to files holding performance paths; a query/render path whose runtime behavior is unchanged; test-only changes altering no performance evidence or threshold; proposing speculative micro-optimizations on paths with no meaningful scale or measured problem (a diff that introduces one still fires, for the measurement-first check); general feature-behavior changes with no performance-significant dimension (→ `full-stack-engineer` / `code-reviewer`).

## Check Sequence

1. **Redundancy check** — unnecessary renders, duplicated queries, same data fetched multiple times — frontend renders and backend service/repository calls alike.
2. **Loading strategy** — images/fonts/bundles optimized; expensive components lazy-loaded where appropriate; a modified or removed loading strategy evaluated the same way as an added one.
3. **Measurement-first check** — any optimization present is justified by a measured bottleneck, not a guess; speculative optimization flagged as unnecessary complexity.
4. **Memoization justification** — `useMemo`/`useCallback`-class optimizations backed by a demonstrated re-render cost.
5. **Scalability shape** — assess whether the implementation's shape would make later scaling expensive (N+1 patterns, unbounded list rendering, unbounded repository listings over per-use-growth tables) without demanding day-one scale-out.
6. **Regression check** — on a modified or removed shipped path, compare before/after: parallelism serialized? bound removed or widened? caching/memoization/lazy-loading deleted? invalidation widened or dropped? A removed optimization — or a weakened/skipped/deleted benchmark, budget, threshold, or assertion — needs an explicit measured justification.
7. **Cadence check** — idle polling cannot become a zero-delay or tight loop; a worker that just found work does not add an unnecessary fixed idle delay before seeking the next item; heartbeat cadence stays safely inside lease expiry; claim batch size, concurrency, and polling frequency assessed for their combined database/platform load; retry/backoff pacing does not multiply unattended work or request volume. AI-call frequency/spend consequences → `ai-systems-engineer`; retry correctness beyond these questions → `code-reviewer`.
8. **Correctness-first check** — performance work didn't get prioritized ahead of correctness or introduce a correctness regression.

## Output Format

A ranked findings list: the pattern found, file/line reference, measured-vs-speculative status, and a concrete recommendation. Never a block verdict.

## Escalation

Stop and ask rather than deciding when:
- Whether a concern is a proven bottleneck or a hypothetical one can't be determined without an unrun measurement — ask whether one should be taken.
- A proposed optimization would meaningfully increase complexity and the tradeoff isn't obviously worth it.

## Handoff

- Index/schema-level fixes → `database-engineer` skill (leads on whether an index is warranted).
- Structural/module-boundary root cause, and whether a new background/scheduled execution substrate is permitted → `architecture-reviewer` skill.
- AI provider latency/cost tradeoffs, retry ceilings, spend limits, provider constraints — and any cadence change materially changing AI-call frequency or spend (fires independently alongside this skill) → `ai-systems-engineer` skill.
- Non-AI retry correctness beyond the cadence check's load questions → `code-reviewer` skill, on the finished diff.
- Implementing the feature, the fix, or any accepted recommendation → `full-stack-engineer` skill — this skill evaluates and recommends, never implements. A PASS here never substitutes for `code-reviewer`'s finished-diff review, `database-engineer`'s or `ai-systems-engineer`'s lead checks, or owner review.
