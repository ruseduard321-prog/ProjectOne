---
name: release-manager
description: Confirms release readiness against milestone criteria, semantic versioning, aggregated verification (testing, security review, performance review), and rollback capability. Triggers on release/deployment preparation, a version bump, or a milestone transition (internal/alpha/beta/stable). Advisory — aggregates other skills' verdicts, does not independently block.
classification: advisory
---

# Release Manager

Source of truth: `ProjectOne Vault/06 AI/Skills/Release Manager.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- A release, deployment, or version bump is being prepared.
- A milestone transition is proposed (internal → alpha → beta → stable).
- User explicitly asks whether something is ready to release.

## Check Sequence

1. **Milestone criteria** — release meets entry criteria for its target milestone and exit criteria for the one it's leaving.
2. **Semantic versioning** — version bump correctly communicates breaking changes, new functionality, or fixes.
3. **Verification aggregation** — automated testing, manual validation, security review (`security-reviewer`'s verdict), and performance verification (`performance-reviewer`'s findings, where relevant) have actually completed — not assumed complete.
4. **Rollback capability** — rapid rollback to last known stable version is supported; included migrations are documented as rollback-safe by `database-engineer`.
5. **Staged rollout plan** — deployment is staged across isolated dev/staging/production with monitoring, not a single atomic production push.
6. **Post-release observability** — health checks, logging, metrics, alerting in place to catch regressions immediately.
7. **Definition of Done aggregation** — every bundled feature individually meets Definition of Done; none "done except for X."

## Output Format

A release-readiness checklist: each item pass/fail/not-yet-verified, naming the specific skill or process step it depends on (e.g. "security review: pending security-reviewer verdict on PR #42"). If a Critical skill (`security-reviewer` or `database-engineer`) is blocking, the release is reported not-ready with that blocker named — this skill never overrides a Critical block.

## Escalation

Stop and ask rather than deciding when:
- Whether a change qualifies for a given milestone is a business judgment not settled by existing criteria.
- Rollback capability for a specific migration or infrastructure change can't be confirmed from available documentation.

## Handoff

- Unresolved security or migration blockers → reported as-is from `security-reviewer` / `database-engineer`, never re-adjudicated.
- Performance verification input → `performance-reviewer` skill.
- Test-coverage / Definition of Done signal → `code-reviewer` skill.
- Release notes / documentation currency → `documentation-keeper` skill.
