---
name: bug-investigator
description: Performs root-cause analysis on an observed failure whose cause is not yet established, classifies severity, and verifies a proposed fix addresses the actual cause with regression coverage. Triggers on a reported defect, exception or incorrect behavior; a runtime error in application or security-event logs; a test failing locally or in CI; an intermittent failure or a red run that turns green on re-run; a CI job that fails without any test failing; a red FA-02/FA-03 drill handed back by database-engineer; a regression in already-shipped behavior; an operation reporting success without producing its result; expected logs, audit records or background effects going missing; and a proposed fix needing verification before a defect is treated as resolved. Not triggered by unimplemented features, tests failing or skipping by design, documentation-only changes, or ordinary review of a working diff. Advisory — recommends only.
classification: advisory
---

# Bug Investigator

Source of truth: `ProjectOne Vault/06 AI/Skills/Bug Investigator.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on an **observed failure whose cause is not yet established**, never on a diff that merely looks risky.

**Reported and observed defects**

- A defect, exception, or incorrect behavior reported by a user, the owner, or a downstream tool.
- A runtime exception or error in application logs or the security event log — start from the `request_id` correlation id (`apps/api/app/core/logging.py`).
- A regression: shipped behavior stops matching what it did before. Trace backward to the change that introduced it.

**Test and pipeline failures**

- A test fails locally or in CI and the change does not already establish the cause. "Obvious cause" is a finding, not an entry condition.
- A test fails intermittently, or a red run goes green on re-run with nothing changed. A green re-run never disposes of it.
- A CI job fails with no test failure — e.g. `Initialize containers`, service-container readiness, dependency install. `pytest-output.txt` absent means the suite never ran.
- A red FA-02 (`migration_cycle_drill.py`) or FA-03 (`backup_restore_drill.py`) run that `database-engineer` has established is a genuine defect; evidence is the `api-drill-output` artifact.

**Failures that report success**

- An operation reports success without producing its result, or a failure surfaces as a benign state (e.g. an outage rendered as a signed-out session, a retry that clears client state without re-fetching).
- Expected output stops appearing: logs, audit records, security events, or a background/scheduled effect. No report and no red test will exist — a noticed absence is the trigger.

**Fix verification and requests**

- A fix proposed for a defect (diagnosed here, found in CI, or raised in review, including by an external reviewer) needs verification before the defect is treated as resolved.
- Explicitly asked to investigate a bug or failure, or to check whether a fix addresses the cause.

**Not a trigger**

- A feature not yet implemented — a `Build Plan` step not started or `In Progress` is planned work, not a defect.
- A test failing or skipping by design: the `migrated_database` skip banner without PostgreSQL (FA-01), `PROJECTONE_REQUIRE_DATABASE_TESTS` turning that skip into a failure in CI, or a guard test failing because it is enforcing its standard.
- Documentation-only changes, including a red governance-docs sync check → `documentation-keeper`.
- Ordinary review of a working diff with no observed failure → `code-reviewer` / `full-stack-engineer`. Never bug-hunt speculatively.
- A known, accepted limitation already recorded in a step note, ADR, or documented constraint.

## Check Sequence

1. **Reproduction** — confirm the defect reproduces from reported steps/inputs; if not reproducible, say so explicitly rather than guessing. For an intermittent failure, establish frequency and the varying condition (ordering, concurrency, timing, environment, data state) — one passing re-run proves nothing.
2. **Root-cause trace** — trace to the actual origin, not just where the error surfaced, using the evidence that exists: `request_id` correlation id, CI step summary, `api-pytest-output` and `api-drill-output` artifacts. For a regression, work backward to the introducing change.
3. **Severity classification** — rate by impact (data loss, security exposure, user-facing breakage, cosmetic) and scope (single user/workspace/platform-wide).
4. **Domain handoff check** — determine if the root cause is security-, performance-, migration-, or AI-system-relevant and hand off rather than treating it as generic. In the same step, determine whether it is application code at all: if the cause is the CI runner, a service container, an external provider, or environment configuration, name that surface and stop.
5. **Fix verification** — confirm a proposed fix addresses the root cause identified in step 2, not just the reported symptom.
6. **Regression coverage** — confirm a test now exists that would have caught this bug. For an intermittent failure it must target the condition established in step 1, not re-run the previously flaky assertion.
7. **Silent-failure check** — flag as a separate defect if the original failure failed silently.

## Output Format

A root-cause report: reproduction steps, actual cause vs. symptom, severity rating, and (once a fix is proposed) a verification note on cause-vs-fix match and regression coverage. Domain handoffs are named explicitly, not investigated further by this skill; a cause outside application code is reported as such, naming the owning surface. Never a block verdict.

## Escalation

Stop and ask rather than deciding when:
- The defect can't be reproduced with available information — state plainly what's missing rather than guessing at a cause.
- The failure is intermittent and the varying condition can't be established — report it as an open intermittent defect with what was observed and what would establish it; never close it as non-reproducible and never let a green re-run stand as the answer.
- Severity is ambiguous because actual production blast radius isn't knowable from available context.

## Handoff

- Fix implementation → `full-stack-engineer` skill. Diagnosis stays here; the fix is not written here, however small.
- Security-vulnerability root cause → `security-reviewer` skill (Critical, leads from that point).
- Performance-regression root cause → `performance-reviewer` skill.
- Migration/schema-caused root cause → `database-engineer` skill (Critical); it hands back a red FA-02 drill once established as a genuine defect.
- AI cost-governance, retry/execution-ceiling, or provider-fallback root cause → `ai-systems-engineer` skill.
- Independent review of the implemented fix → `code-reviewer` skill.
- Severity input for release readiness → `release-manager` skill; it judges whether a release proceeds, this skill does not.
