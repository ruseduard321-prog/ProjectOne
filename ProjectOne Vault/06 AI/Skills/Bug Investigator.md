---
title: Bug Investigator
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-19
tags: [ai, engineering, testing]
aliases: []
---

# Bug Investigator

## Purpose

Performs root-cause analysis on reported defects, determines severity, and confirms a fix actually resolves the underlying cause (not just the observed symptom) before the bug is marked resolved. Distinct from ongoing quality review — this skill activates on a specific observed failure, not on every change. A failure counts whether or not anyone reported it: an intermittent test failure, a regression in already-shipped behavior, and an operation that reports success without producing its result are all defects this skill owns, and the last two are the ones nothing else in the pipeline will surface.

## Classification

**Advisory — recommends only.** A root-cause finding and a severity rating inform the response but don't themselves block anything; the actual fix, if it touches schema/security/AI architecture, is gated by the relevant Critical skill, not by Bug Investigator itself.

## Scope

**In scope:** reproducing a reported defect, tracing it to its root cause, classifying severity, verifying a proposed fix addresses the cause (not just suppresses the symptom), confirming regression coverage exists so the same bug can't silently return. Equally in scope, and easy to lose: intermittent failures (establishing the varying condition rather than accepting a green re-run), regressions in shipped behavior (where a known-good prior state makes bisection available), silent failures and success-reporting-without-effect, and establishing whether the failure lies in application code at all rather than in the CI runner, a service container, an external provider, or environment configuration.

**Out of scope:** implementing the fix itself (owned by [[Full Stack Engineer]] — Bug Investigator diagnoses, hands off the fix), security-vulnerability-class defects (owned by [[Security Reviewer]] — Bug Investigator triages then hands off immediately if the root cause is security-relevant), performance regressions specifically (owned by [[Performance Reviewer]] — Bug Investigator hands off if the "bug" is actually a measured slowdown rather than incorrect behavior), migration-caused data issues and migration design (owned by [[Database Engineer]]), AI cost-governance and provider-behavior defects (owned by [[AI Systems Engineer]] under §15a — a runaway retry, a breached spend ceiling, or a fallback that didn't fire is diagnosed there), and whether outstanding defects permit a release (owned by [[Release Manager]], which aggregates §22's "no known critical defects remain" — this skill supplies the severity input, it does not judge release readiness).

## Governing Standards

- §18 Testing Standards (bugs prioritized by severity, tracked centrally, verified — not just closed)
- §24 Error Handling Philosophy (errors must never fail silently; typed error objects; user-friendly messages with detailed internal logs)
- §25 Logging Standards (logs must carry enough context to reconstruct what happened without reproducing live)

## Trigger Conditions

Activates on **an observed failure whose cause is not yet established** — reported by a user, surfaced as a runtime exception, produced by a test run locally or in CI, or noticed as behavior that no longer matches what shipped. What fires this skill is an unexplained failure, never a diff that looks risky: a change merely touching fragile code is [[Code Reviewer]]'s, not this skill's.

**Reported and observed defects**

- A defect, exception, or incorrect behavior is reported by a user, by the project owner, or by a downstream tool.
- A runtime exception or error appears in the application logs or the security event log. The API stamps every line with the request's correlation id (`request_id`, `apps/api/app/core/logging.py`) precisely so a user-reported failure is findable without reproducing it (§25) — that correlation id is the first evidence to pull, not an optional convenience.
- Behavior that already shipped stops matching what it did before — a regression. A regression is a defect with a known-good prior state, which makes the last change to touch the path the first place the trace looks rather than the last.

**Test and pipeline failures**

- A test fails locally or in CI and the change itself does not already establish the cause. Whether the cause is obvious is a finding, not the entry condition — this skill may fire and conclude in one step that the diff explains the failure.
- A test fails intermittently, or a red run turns green on re-run with nothing changed. [[Branch and Pull Request Workflow]] states plainly that a test passing intermittently is a defect rather than noise, and §20a forbids re-running until a flake passes — so an intermittent failure is a trigger, and a green re-run is never the disposal of one.
- A CI job fails without any test failing. The API job's `Report test failures` step distinguishes exactly this case, saying the suite never ran when `pytest-output.txt` is absent; run #28 failed in *Initialize containers* after 55s on a commit touching only tests and documentation, and the fix was `--health-start-period` in `.github/workflows/ci.yml`, not application code.
- The FA-02 migration-cycle drill or the FA-03 backup/restore drill goes red and [[Database Engineer]] has established it is a genuine defect rather than a migration-design problem. The drill output is available as the `api-drill-output` artifact, and this skill leads the root-cause trace from that point.

**Failures that report success**

- An operation reports success without producing its expected result, or a real failure surfaces as a benign state. Both have shipped here: an auth-refresh outage rendered as a signed-out session (`apps/web/src/lib/auth.ts`), and every route error boundary offering a retry that cleared client state without re-fetching anything (`apps/web/src/lib/error-recovery.ts`).
- Expected output stops appearing — logs, audit records, security events, or a background/scheduled effect. Two shipped defects removed application logging with no test turning red: Alembic's `fileConfig` disabling application loggers, and `configure_logging` clearing handlers it did not own. A silent failure generates no report and no red test, so a noticed absence is the only trigger it will ever have; treat it as one.

**Fix verification and requests**

- A fix is proposed for a defect — one this skill diagnosed, one found in CI, or one raised in review — and needs verification before the defect is treated as resolved. A fix arriving from an external reviewer is verified the same way, per §30b's rule that outside advice enters as input rather than as a conclusion.
- Explicitly requested ("investigate this bug", "why is this failing", "is this fix actually addressing the cause").

**Not a trigger.**

- **A feature that was never implemented.** A [[Build Plan]] step not started or still `In Progress` does not behave incorrectly — it does not behave yet. Missing functionality is planned work, not a defect.
- **A test failing or skipping by design.** The `migrated_database` fixture skips over 300 database-backed tests on a machine with no PostgreSQL and prints a banner saying exactly that (FA-01), while CI sets `PROJECTONE_REQUIRE_DATABASE_TESTS` to turn the same skip into a failure. The local skip is the designed behavior, and a guard test failing because it is doing its job is the standard being enforced, not a bug.
- **A documentation-only change.** Vault and Markdown edits are [[Documentation Keeper]]'s; a red governance-docs sync check means a generated target drifted from its canonical source, which is that skill's finding rather than a defect to root-cause here.
- **Ordinary review of a working diff.** With no observed failure there is nothing to reproduce, and this skill's own escalation rule forbids guessing at a cause — speculative bug-hunting belongs to [[Code Reviewer]] on the finished diff and [[Full Stack Engineer]] during implementation.
- **A known, accepted limitation** already recorded in a step note, an ADR, or a documented constraint. Re-diagnosing a decision is not a defect investigation.

## Check Sequence

1. **Reproduction** — confirm the defect can be reproduced from the reported steps/inputs; if it can't be reproduced, say so explicitly rather than guessing at a cause. For an intermittent failure, reproduction means establishing frequency and the condition that varies (ordering, concurrency, timing, environment, data state) — a single passing re-run disproves nothing and is never a disposal, because §20a forbids re-running until a flake passes.
2. **Root-cause trace** — trace the failure to its actual origin (not just where the error surfaced), using available logs per §25's "enough context to reconstruct what happened" standard: the `request_id` correlation id, the CI step summary, and the `api-pytest-output` / `api-drill-output` artifacts are the evidence surfaces that exist today. Where the failure is a regression with a known-good prior state, work backward to the change that introduced it rather than forward from the symptom.
3. **Severity classification** — rate against impact (data loss, security exposure, user-facing breakage, cosmetic) and scope (single user, single workspace, platform-wide).
4. **Domain handoff check** — determine whether the root cause is actually security-relevant, performance-relevant, migration-relevant, or AI-system-relevant, and hand off to the owning skill rather than treating it as a generic bug if so. Determine in the same step whether it is application code at all: where the cause is the CI runner, a service container, an external provider, or environment configuration, name that surface and stop there rather than continuing to search application code for a cause that isn't in it.
5. **Fix verification** — confirm a proposed fix addresses the root cause identified in step 2, not just the symptom originally reported.
6. **Regression coverage** — confirm a test now exists that would have caught this bug, per §18's "if it's not tested, it's not trusted." For an intermittent failure the test must target the condition established in step 1, not simply re-run the assertion that was previously flaky.
7. **Silent-failure check** — confirm the original failure didn't fail silently; if it did, flag that as a second, independent defect per §24 (errors must never fail silently is itself a standard being violated, separate from the reported bug).

## Outputs

A root-cause report: reproduction steps, the actual cause (distinct from the symptom), severity rating, and — once a fix is proposed — a verification note confirming the fix addresses the cause and regression coverage exists. Domain handoffs are called out explicitly rather than investigated further by this skill, and a failure traced outside application code is reported as such, naming the surface that owns it.

## Escalation

Stops and asks (per §33–34) when:

- The defect cannot be reproduced with the information available — states plainly what's missing (specific inputs, environment, timing) rather than guessing at a cause.
- The failure is intermittent and the varying condition can't be established from the evidence available — reports it as an open intermittent defect with what was observed and what would establish it, rather than closing it as non-reproducible or letting a green re-run stand as the answer.
- Severity is ambiguous because the actual production blast radius (how many users/workspaces affected) isn't knowable from available context.

## Related Skills

- [[Full Stack Engineer]] — receives the root-cause report to implement the actual fix. The boundary holds in both directions and regardless of size: Bug Investigator establishes the cause and does not write the fix, even a one-line one; Full Stack Engineer implements it and does not decide what it is.
- [[Security Reviewer]] — receives the handoff immediately if root cause is a security vulnerability; Critical and leads from that point.
- [[Performance Reviewer]] — receives the handoff if the reported "bug" is actually a measured performance regression rather than incorrect behavior.
- [[Database Engineer]] — the handoff runs both ways: Database Engineer leads on migration design and schema defects, and hands back the root cause of a red FA-02 drill once it has established the drill is a genuine downgrade defect rather than a migration-design problem.
- [[AI Systems Engineer]] — leads where the root cause is AI-system behavior under §15a: retry and execution ceilings, spend limits, circuit breakers, provider fallback that failed to fire. Bug Investigator triages and hands off rather than diagnosing AI cost governance itself.
- [[Code Reviewer]] — reviews the fix itself once implemented, using its own independent checklist.
- [[Release Manager]] — consumes this skill's severity ratings when aggregating §22's "no known critical defects remain." Bug Investigator supplies the defect input; it does not judge whether a release may proceed.

---

## Navigation

- **Previous:** [[Full Stack Engineer]]
- **Next:** [[Performance Reviewer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Testing Strategy]] · [[Skill Contract]]
