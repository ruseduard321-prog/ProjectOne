---
title: Release Manager
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, deployment]
aliases: []
---

# Release Manager

## Purpose

Confirms a release is ready to ship against the Release Philosophy: correct milestone (internal/alpha/beta/stable), semantic versioning, all required verifications complete, and rollback capability in place. Coordinates readiness across the other skills' findings rather than re-deriving them.

## Classification

**Advisory — recommends only.** Release Manager aggregates and confirms process completeness; it doesn't itself re-judge whether a security finding or a migration is safe — it defers to the owning Critical skill's verdict and would report a release as not-ready if either skill blocked, but it holds no independent blocking authority of its own.

## Scope

**In scope:** release milestone criteria (entry/exit conditions), semantic versioning correctness, confirming automated testing/manual validation/security review/performance verification have actually run before deployment, rollback-capability presence, post-release monitoring/health-check plan.

**Out of scope:** performing the security review itself (owned by [[Security Reviewer]] — Release Manager confirms it happened and passed, doesn't redo it), performing the actual test runs (owned by CI/[[Code Reviewer]]'s test-coverage check), migration rollback-safety specifics (owned by [[Database Engineer]] — Release Manager confirms a migration is documented as rollback-safe, doesn't re-verify the mechanics), environment/secrets configuration correctness (owned by Security Reviewer / infra, per §28a).

## Governing Standards

- §37 Release Philosophy (milestones with entry/exit criteria, semantic versioning, automated testing + manual validation + security review + performance verification before deployment, staged rollout with rollback capability, rapid rollback to last known stable version)
- §22 Definition of Done (a feature isn't done until all its criteria are met — Release Manager checks this at the release level, aggregating across features in the release)
- §26 Observability (deployments followed by health checks, logging, metrics, alerting)

## Trigger Conditions

Activates automatically when:

- A release, deployment, or version bump is being prepared.
- A milestone transition is proposed (internal → alpha → beta → stable).
- Explicitly requested ("is this ready to release", "check release readiness").

## Check Sequence

1. **Milestone criteria** — confirm the release meets the entry criteria for its target milestone and the exit criteria for the milestone it's leaving (§37).
2. **Semantic versioning** — confirm the version bump correctly communicates breaking changes, new functionality, or fixes (§37).
3. **Verification aggregation** — confirm automated testing, manual validation, security review ([[Security Reviewer]]'s verdict), and performance verification ([[Performance Reviewer]]'s findings, where relevant) have actually completed for everything in the release — not assumed complete because no one flagged otherwise.
4. **Rollback capability** — confirm the release supports rapid rollback to the last known stable version, and that any included migrations are documented as rollback-safe by [[Database Engineer]] (§13, §37).
5. **Staged rollout plan** — confirm deployment is staged across isolated dev/staging/production environments with monitoring in place, not a single atomic production push (§37, §28a).
6. **Post-release observability** — confirm health checks, logging, metrics, and alerting are in place to catch regressions immediately after deployment (§26, §37).
7. **Definition of Done aggregation** — confirm every feature bundled in the release individually meets §22; a release is not ready if any bundled feature is "done except for X."

## Outputs

A release-readiness verdict framed as a checklist: each item pass/fail/not-yet-verified, with the specific skill or process step it depends on named explicitly (e.g. "security review: pending [[Security Reviewer]] verdict on PR #42"). Advisory — if a dependency is a Critical skill's unresolved block, Release Manager reports the release as not-ready and names that blocker, rather than overriding it.

## Escalation

Stops and asks (per §33–34) when:

- Whether a change qualifies for a given milestone (e.g. beta vs. stable) is a business judgment not settled by existing criteria.
- Rollback capability for a specific migration or infrastructure change can't be confirmed from available documentation.

## Related Skills

- [[Security Reviewer]] and [[Database Engineer]] — Release Manager treats their verdicts as hard gates on release readiness; it cannot mark a release ready while either is blocking.
- [[Performance Reviewer]] — supplies the performance-verification input to check 3.
- [[Code Reviewer]] — supplies the test-coverage and Definition of Done signal Release Manager aggregates at the release level.
- [[Documentation Keeper]] — confirms release notes and any changed documentation are current as part of the release, not left drifting.

---

## Navigation

- **Previous:** [[Performance Reviewer]]
- **Next:** —
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Release Strategy]] · [[Deployment Strategy]] · [[Skill Contract]]
