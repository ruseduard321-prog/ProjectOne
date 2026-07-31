---
title: Documentation Keeper
category: AI/Skills
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, documentation]
aliases: []
---

# Documentation Keeper

## Purpose

Keeps the vault internally consistent after any change to it: frontmatter correctness, wiki-link integrity, MOC/index membership, and Navigation-block completeness. Exists so structural maintenance (the single largest source of manual rework in this project's history) happens automatically instead of in a dedicated cleanup pass after the fact.

## Classification

**Advisory — recommends only.** Documentation drift is a real cost (a misleading doc is worse than no doc, per §19) but it's a slow-accumulating one, not an irreversible one — a broken link or a stale index entry is always fixable after the fact with no data lost. Blocking on it would slow down every vault edit for a risk class that isn't remotely as high-stakes as [[Security Reviewer]]'s or [[Database Engineer]]'s.

## Scope

**In scope:** YAML frontmatter shape and correctness, wiki-link resolution (no broken `[[links]]`), MOC and index membership for new/moved notes, Navigation-block presence and correctness (Previous/Next/Parent/Related), `status` field accuracy (draft → stable → archived), template consistency in `13 Templates/`.

**Out of scope:** the technical accuracy or completeness of a document's actual content (that's a review call for whoever owns the subject matter), code-level documentation like docstrings/comments (owned by [[Code Reviewer]]), deciding *whether* new architecture should be documented as an ADR (owned by [[Code Reviewer]]/[[Security Reviewer]]/[[Database Engineer]] flagging it; Documentation Keeper handles the mechanics once that's decided).

## Governing Standards

- §19 Documentation Standards (docs are part of the product; drift is treated as a bug; affected docs must be identified in the same change)
- Vault [[README]] (frontmatter schema, naming conventions, MOC/index/navigation conventions — this is Documentation Keeper's most detailed operating manual, more specific than CLAUDE.md itself on vault mechanics)

## Trigger Conditions

Activates automatically when a change:

- Adds, moves, renames, or deletes any file under `ProjectOne Vault/`.
- Adds or modifies a wiki-link.
- Changes a folder's structure or numbering (as happened during the Phase 6 renumbering).
- Is explicitly requested ("check the vault for broken links", "update the indexes").

## Check Sequence

1. **Frontmatter completeness** — every note has `title, category, status, version, last_updated, tags`; content notes converted from source PDFs also carry `source_pdf` (per [[README]]).
2. **Wiki-link resolution** — every `[[target]]` or `[[target|alias]]` resolves to an existing note title or a frontmatter alias; folder-reference links (e.g. `[[13 Templates]]`) are recognized as valid, not falsely flagged.
3. **MOC/index membership** — a new note is linked from at least one MOC and appears in the relevant index(es) ([[Global Index]], [[Alphabetical Index]], [[Category Index]], and [[Documentation Index]] if it's vault infrastructure). A note reachable only from its own folder listing is effectively lost (§19, README "How to Maintain the Vault").
4. **Navigation block** — every note ends with a Navigation block; Previous/Next reflect actual reading order within its series, Parent points to its real MOC, Related Notes are still valid links.
5. **Status accuracy** — a note describing a settled decision is `stable`, not left at `draft`; a superseded note is `archived` and physically in `99 Archive/` if appropriate.
6. **Cross-copy consistency** — where a document is deliberately mirrored, the body content is byte-identical; only frontmatter/navigation differ. For CLAUDE.md this is enforced mechanically, not by review: `00 Governance/CLAUDE.md` is the canonical source and the root `CLAUDE.md` is generated from it by `scripts/sync-claude-md.sh`. Verify with `./scripts/sync-claude-md.sh --check`; never hand-edit the root file to resolve a mismatch.
7. **No duplicate canonical content** — a concept documented once is linked to elsewhere, never re-explained in a second note (§19, README "One Template Library, Not Two" as the precedent case).

## Outputs

A findings list grouped by file, each with the specific gap (missing frontmatter field, broken link, missing index entry, stale status) and the exact fix. For a renumbering or bulk-move operation, additionally outputs a before/after file-count reconciliation (as was done for the Phase 6 renumbering: 111 → 108 notes, accounting for 3 deliberately deleted pointer notes, 46 PDFs unchanged) so scale of the operation is verifiable at a glance.

## Escalation

Stops and asks (per §33–34) when:

- A note appears orphaned but it's unclear which MOC it should belong to (a genuine categorization judgment, not a mechanical fix).
- Two notes appear to duplicate the same content and it's unclear which is canonical.
- A structural change (renumbering, consolidation) is large enough that Documentation Keeper should propose the mapping before executing it, per the same standard CLAUDE.md applies to any high-blast-radius change — even though the change itself is reversible, a large mechanical pass is cheaper to get right once than to redo.

## Related Skills

- [[Code Reviewer]] — hands off the "documentation currency" flag (its own check step 6) to Documentation Keeper for actual remediation.
- All other skills — any skill whose check sequence references a CLAUDE.md section or vault note relies on Documentation Keeper to keep those references valid.

---

## Navigation

- **Previous:** [[AI Systems Engineer]]
- **Next:** —
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[README]] · [[Documentation Index]]
