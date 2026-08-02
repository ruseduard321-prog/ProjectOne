---
title: DOC-01 Align ADR Template with CLAUDE.md
category: Development/Build Step
status: draft
version: "1.0"
last_updated: 2026-08-03
tags: [documentation, governance, workflow, build-step]
step_id: DOC-01
step_status: Not Started
detail_level: full
---

# DOC-01 — Align ADR Template with CLAUDE.md

**Status:** Not Started
**Type:** Documentation task, not a Build Plan step — see [[#Why This Is Not a Build Plan Step]].
**Raised by:** the project owner on 2026-08-03, after the divergence surfaced while writing [[ADR-002 Trusted Proxy and Client Address Resolution]].

## The Divergence

[[CLAUDE|CLAUDE.md]] §7 defines the ADR lifecycle explicitly:

> `Draft` (being written, not yet binding) → `Review` (circulated for feedback, not yet binding) → `Accepted` (binding — implementation may begin) or `Rejected` (not adopted, kept for record). An accepted ADR later reversed becomes `Deprecated` or `Superseded`.

[[ADR Template]] does not match it. Its frontmatter carries `status: proposed`, and its Status section offers `{{Proposed | Accepted | Superseded | Deprecated}}`.

Three specific problems:

| Issue | Template | CLAUDE.md §7 |
|---|---|---|
| Initial state | `proposed` | `Draft` |
| Missing state | — | `Review` |
| Missing state | — | `Rejected` |

**`Rejected` is the consequential omission.** §7 keeps rejected ADRs "for record", which is much of what an ADR archive is *for*: the decision not taken, and why, is what stops the same option being re-proposed every year. A template offering no way to express it invites deletion instead.

**The constitution is the source of truth.** The template is wrong and gets corrected; §7 is not amended to match the template.

## Why This Is Not a Build Plan Step

The [[Build Plan]] is the ordered sequence taking ProjectOne to first public release, and each step is sized for a session and produces working software. This is a two-file documentation correction with no code, no validation beyond reading, and no dependency on any step. Inserting it into that sequence would misrepresent both — it would claim a slot in a release plan that a template fix does not need, and it would sit blocking steps that have nothing to do with it.

It is also **operational policy, not architecture** ([[CLAUDE|CLAUDE.md]] §39): it changes how a decision is recorded, not what was decided. No ADR is required to fix the ADR template — which would be circular in a way worth noticing.

## Tasks

1. **Correct [[ADR Template]]'s frontmatter** — `status: draft`, matching §7's initial state and the lowercase convention every other vault note uses in frontmatter.
2. **Correct the Status section** to offer the full lifecycle: `Draft | Review | Accepted | Rejected | Deprecated | Superseded`.
3. **Add a one-line gloss per state**, so the template teaches the lifecycle rather than assuming the reader has §7 open. Take the wording from §7 rather than paraphrasing it — a paraphrase is a second definition that can drift.
4. **State the gate the template currently leaves implicit:** implementation may not begin until an ADR is `Accepted`, and the project owner is the only approver. This is the rule that actually governs behaviour, and a template that omits it invites the mistake it exists to prevent.
5. **Check [[ADR-001 Technology Stack]] and [[ADR-002 Trusted Proxy and Client Address Resolution]]** against the corrected template and note any divergence. Both are `Accepted`, so neither is expected to change — this is a consistency check, not a rewrite.
6. **Check whether any other note describes the ADR lifecycle** and would now contradict the corrected template ([[CLAUDE|CLAUDE.md]] §19). [[Home]] and [[Global Index]] both reference ADRs; confirm neither states a status vocabulary of its own.

## Explicitly Out of Scope

- **Amending [[CLAUDE|CLAUDE.md]] §7.** The constitution is correct; the template diverged from it.
- **Restructuring the ADR format** — sections, ordering, required content. Only the status vocabulary is wrong.
- **Retrofitting existing ADRs** beyond the consistency check in Task 5.

## Validation

- [[ADR Template]]'s frontmatter and Status section both offer exactly the states [[CLAUDE|CLAUDE.md]] §7 names — no more, no fewer.
- A new ADR created from the template starts in a state §7 recognises.
- No remaining note describes an ADR status vocabulary contradicting §7, confirmed by searching the vault for the term `proposed` in an ADR context.

## Definition of Done

[[ADR Template]] matches [[CLAUDE|CLAUDE.md]] §7's lifecycle exactly, including `Review` and `Rejected`; the approval gate is stated in the template; existing ADRs are confirmed consistent; and no other note contradicts the corrected vocabulary.

**Not a Critical change** ([[CLAUDE|CLAUDE.md]] §21) — it touches no schema, auth, security control, API contract or infrastructure. It needs no owner approval gate beyond the owner having asked for it.

---

## Navigation

- **Parent:** [[Development MOC]]
- **Related Notes:** [[ADR Template]] · [[CLAUDE|CLAUDE.md]] · [[ADR-001 Technology Stack]] · [[ADR-002 Trusted Proxy and Client Address Resolution]]
