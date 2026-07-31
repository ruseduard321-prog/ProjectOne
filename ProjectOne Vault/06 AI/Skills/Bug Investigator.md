---
title: Bug Investigator
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, engineering, testing]
aliases: []
---

# Bug Investigator

## Purpose

Performs root-cause analysis on reported defects, determines severity, and confirms a fix actually resolves the underlying cause (not just the observed symptom) before the bug is marked resolved. Distinct from ongoing quality review — this skill activates on a specific reported failure, not on every change.

## Classification

**Advisory — recommends only.** A root-cause finding and a severity rating inform the response but don't themselves block anything; the actual fix, if it touches schema/security/AI architecture, is gated by the relevant Critical skill, not by Bug Investigator itself.

## Scope

**In scope:** reproducing a reported defect, tracing it to its root cause, classifying severity, verifying a proposed fix addresses the cause (not just suppresses the symptom), confirming regression coverage exists so the same bug can't silently return.

**Out of scope:** implementing the fix itself (owned by [[Full Stack Engineer]] — Bug Investigator diagnoses, hands off the fix), security-vulnerability-class defects (owned by [[Security Reviewer]] — Bug Investigator triages then hands off immediately if the root cause is security-relevant), performance regressions specifically (owned by [[Performance Reviewer]] — Bug Investigator hands off if the "bug" is actually a measured slowdown rather than incorrect behavior), migration-caused data issues (owned by [[Database Engineer]]).

## Governing Standards

- §18 Testing Standards (bugs prioritized by severity, tracked centrally, verified — not just closed)
- §24 Error Handling Philosophy (errors must never fail silently; typed error objects; user-friendly messages with detailed internal logs)
- §25 Logging Standards (logs must carry enough context to reconstruct what happened without reproducing live)

## Trigger Conditions

Activates automatically when:

- A defect, exception, or unexpected behavior is reported.
- A test failure appears in CI with no immediately obvious cause.
- A fix is proposed for a previously reported bug and needs verification before being marked resolved.
- Explicitly requested ("investigate this bug", "why is this failing").

## Check Sequence

1. **Reproduction** — confirm the defect can be reproduced from the reported steps/inputs; if it can't be reproduced, say so explicitly rather than guessing at a cause.
2. **Root-cause trace** — trace the failure to its actual origin (not just where the error surfaced), using available logs per §25's "enough context to reconstruct what happened" standard.
3. **Severity classification** — rate against impact (data loss, security exposure, user-facing breakage, cosmetic) and scope (single user, single workspace, platform-wide).
4. **Domain handoff check** — determine whether the root cause is actually security-relevant, performance-relevant, or migration-relevant, and hand off to the owning skill rather than treating it as a generic bug if so.
5. **Fix verification** — confirm a proposed fix addresses the root cause identified in step 2, not just the symptom originally reported.
6. **Regression coverage** — confirm a test now exists that would have caught this bug, per §18's "if it's not tested, it's not trusted."
7. **Silent-failure check** — confirm the original failure didn't fail silently; if it did, flag that as a second, independent defect per §24 (errors must never fail silently is itself a standard being violated, separate from the reported bug).

## Outputs

A root-cause report: reproduction steps, the actual cause (distinct from the symptom), severity rating, and — once a fix is proposed — a verification note confirming the fix addresses the cause and regression coverage exists. Domain handoffs are called out explicitly rather than investigated further by this skill.

## Escalation

Stops and asks (per §33–34) when:

- The defect cannot be reproduced with the information available — states plainly what's missing (specific inputs, environment, timing) rather than guessing at a cause.
- Severity is ambiguous because the actual production blast radius (how many users/workspaces affected) isn't knowable from available context.

## Related Skills

- [[Full Stack Engineer]] — receives the root-cause report to implement the actual fix.
- [[Security Reviewer]] — receives the handoff immediately if root cause is a security vulnerability; Critical and leads from that point.
- [[Performance Reviewer]] — receives the handoff if the reported "bug" is actually a measured performance regression rather than incorrect behavior.
- [[Database Engineer]] — receives the handoff if the root cause traces to a migration or schema issue.
- [[Code Reviewer]] — reviews the fix itself once implemented, using its own independent checklist.

---

## Navigation

- **Previous:** [[Full Stack Engineer]]
- **Next:** [[Performance Reviewer]]
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[Testing Strategy]] · [[Skill Contract]]
