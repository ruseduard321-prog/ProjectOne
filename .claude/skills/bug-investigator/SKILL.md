---
name: bug-investigator
description: Performs root-cause analysis on reported defects, classifies severity, and verifies a proposed fix addresses the actual cause with regression coverage. Triggers on a reported defect/exception, an unexplained CI test failure, or a fix proposed for a previously reported bug needing verification. Advisory — recommends only.
classification: advisory
---

# Bug Investigator

Source of truth: `ProjectOne Vault/06 AI/Skills/Bug Investigator.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

- A defect, exception, or unexpected behavior is reported.
- A test failure appears in CI with no immediately obvious cause.
- A fix is proposed for a previously reported bug and needs verification before being marked resolved.
- User explicitly asks to investigate a bug or failure.

## Check Sequence

1. **Reproduction** — confirm the defect reproduces from reported steps/inputs; if not reproducible, say so explicitly rather than guessing.
2. **Root-cause trace** — trace to the actual origin, not just where the error surfaced, using available logs.
3. **Severity classification** — rate by impact (data loss, security exposure, user-facing breakage, cosmetic) and scope (single user/workspace/platform-wide).
4. **Domain handoff check** — determine if the root cause is actually security-, performance-, or migration-relevant and hand off rather than treating it as generic.
5. **Fix verification** — confirm a proposed fix addresses the root cause identified in step 2, not just the reported symptom.
6. **Regression coverage** — confirm a test now exists that would have caught this bug.
7. **Silent-failure check** — flag as a separate defect if the original failure failed silently.

## Output Format

A root-cause report: reproduction steps, actual cause vs. symptom, severity rating, and (once a fix is proposed) a verification note on cause-vs-fix match and regression coverage. Domain handoffs are named explicitly, not investigated further by this skill. Never a block verdict.

## Escalation

Stop and ask rather than deciding when:
- The defect can't be reproduced with available information — state plainly what's missing rather than guessing at a cause.
- Severity is ambiguous because actual production blast radius isn't knowable from available context.

## Handoff

- Fix implementation → `full-stack-engineer` skill.
- Security-vulnerability root cause → `security-reviewer` skill (Critical, leads from that point).
- Performance-regression root cause → `performance-reviewer` skill.
- Migration/schema-caused root cause → `database-engineer` skill.
- Independent review of the implemented fix → `code-reviewer` skill.
