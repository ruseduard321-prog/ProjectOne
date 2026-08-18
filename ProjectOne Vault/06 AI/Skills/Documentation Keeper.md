---
title: Documentation Keeper
category: AI/Skills
status: stable
version: "1.1"
last_updated: 2026-08-18
tags: [ai, documentation]
aliases: []
---

# Documentation Keeper

## Purpose

Keeps the vault internally consistent after any change to it: frontmatter correctness, wiki-link integrity, MOC/index membership, and Navigation-block completeness. Exists so structural maintenance (the single largest source of manual rework in this project's history) happens automatically instead of in a dedicated cleanup pass after the fact.

The consistency surface extends past the vault's own folder exactly where the vault makes a promise to the rest of the repository: wiki-links in repository Markdown outside `ProjectOne Vault/` resolve into the vault (`infrastructure/README.md`, `infrastructure/process-model.md` and `scripts/README.md` carry such links today), the root governance documents are generated from canonical vault sources by the transformation `scripts/sync-governance-docs.config.json` configures, and the Build Plan records each step's status in places that must agree with each other and with what actually shipped. Those are documentation contracts, and this skill guards the contracts — not every Markdown file that happens to exist.

## Classification

**Advisory — recommends only.** Documentation drift is a real cost (a misleading doc is worse than no doc, per §19) but it's a slow-accumulating one, not an irreversible one — a broken link or a stale index entry is always fixable after the fact with no data lost. Blocking on it would slow down every vault edit for a risk class that isn't remotely as high-stakes as [[Security Reviewer]]'s or [[Database Engineer]]'s.

## Scope

**In scope:** YAML frontmatter shape and correctness, wiki-link resolution (no broken `[[links]]`) across every repository Markdown file — inside `ProjectOne Vault/` and out, MOC and index membership for new/moved notes, Navigation-block presence and correctness (Previous/Next/Parent/Related), `status` field accuracy (draft → stable → archived), template consistency in `13 Templates/`, governed-document parity (every configured target matching the transformation `scripts/sync-governance-docs.config.json` defines and the live sync mechanism produces), and Build Plan status integrity (representation agreement and lifecycle closure — mechanical verification of [[Execution Protocol]]'s rules, which that protocol owns).

**Out of scope:** the technical accuracy or completeness of a document's actual content (that's a review call for whoever owns the subject matter), code-level documentation like docstrings/comments (owned by [[Code Reviewer]]), deciding *whether* new architecture should be documented as an ADR (owned by [[Code Reviewer]]/[[Security Reviewer]]/[[Database Engineer]] flagging it; Documentation Keeper handles the mechanics once that's decided), CI workflow configuration including the `governance docs (sync check)` job in `.github/workflows/ci.yml` (owned by [[Code Reviewer]]'s CI trigger and the project owner — the required status check, not this skill, is the enforcing gate), and deciding what a Build Plan step's status *should* be ([[Execution Protocol]] and the executing session own that; this skill verifies the recorded state against itself and against the evidence, and escalates conflicts).

## Governing Standards

- §19 Documentation Standards (docs are part of the product; drift is treated as a bug; affected docs must be identified in the same change)
- Vault [[README]] (frontmatter schema, naming conventions, MOC/index/navigation conventions — this is Documentation Keeper's most detailed operating manual, more specific than CLAUDE.md itself on vault mechanics)
- [[Execution Protocol]] ("Status lives in two places and must agree. Updating one without the other is a defect." — plus the completion conditions a step must meet before `Done`; the protocol owns these rules, this skill only checks them)
- `scripts/sync-governance-docs.config.json` (authoritative for both the complete list of canonical-source → generated-target pairs and the transformation each target must match — the parity check reads this config, never a hardcoded list or an inferred set of permitted differences)

## Trigger Conditions

Activates on changes to the **documentation contracts this skill guards** — vault structure and note integrity, link integrity, governed-document parity, and build-plan status integrity. A Markdown file merely being edited is never sufficient on its own; what fires this skill is one of these surfaces changing.

**Vault file operations**

- Any file added, moved, renamed, or deleted under `ProjectOne Vault/`. A move, rename, or delete additionally requires the repository-wide inbound-link sweep in check 2 — a link into the vault from outside it (e.g. `infrastructure/process-model.md` → [[STEP-30 Async Job Infrastructure]]) breaks exactly as silently as a link inside it.
- A folder's structure or numbering changes under `ProjectOne Vault/` (as happened during the Phase 6 renumbering).

**Vault note integrity**

- A required frontmatter field is added or removed, or a structural/identity field changes — `title`, `aliases`, `category`, or a note's `status`. Routine maintenance of `version` and `last_updated` alone does not fire.
- A Navigation block is added, modified, or removed.
- A template under `ProjectOne Vault/13 Templates/` changes in a way that alters the convention it documents.

**Wiki-link changes, anywhere in the repository**

- A wiki-link added, modified, or **deleted** in any repository Markdown file — inside `ProjectOne Vault/` or outside it. A deleted link can orphan a note or break Navigation reciprocity just as surely as a broken one can.

**Governed-document surface**

- A canonical source listed in `scripts/sync-governance-docs.config.json` changes — the configured target must be regenerated in the same change and verified with the sync check.
- A generated target listed in that config is edited directly. The direct edit is itself the finding, whatever its content: the fix is never to adjust the target but to port any substantive content into the canonical source and regenerate (check 6, and Escalation where content would otherwise be discarded).
- The sync mechanism changes: `scripts/sync-governance-docs.sh`, `scripts/sync-governance-docs.ps1`, or `scripts/sync-governance-docs.config.json` — including a document entry added or removed, which changes what the governed surface *is*. The scripts' code quality is [[Code Reviewer]]'s; this skill verifies the parity contract still holds and the documentation describing it is still true.

**Build Plan status integrity**

- A step's status changes in any place it is recorded — the step note's `step_status` frontmatter or `**Status:**` line under `09 Development/Build Plan/Steps/`, or the step's row in the [[Build Plan]] index — whether or not the other places changed too.
- A step is presented as complete, ready to close, or merged — a merged or referenced Pull Request, a squash commit on `main`, a Step Completion Record, or the session presenting the step as finished — **even when no recorded status changed**. The STEP-29 and STEP-30 closures (PRs #24 and #27) are this exact case: note and index still agreed on `In Progress` after the merge, so a trigger on recorded changes alone would never have fired.

[[Execution Protocol]] owns the rules; this skill verifies mechanically and never decides what the status should be.

**Explicit request**

- Explicitly requested ("check the vault for broken links", "update the indexes", "is the build plan status consistent").

**Not a trigger.**

- A body-prose edit to an existing vault note that changes no wiki-link, no required or identity frontmatter field, no Navigation block, and no status — subject-matter content is its owner's review call, not this skill's. (A canonical governance source is the exception above: any change to it obligates regeneration.)
- Routine frontmatter maintenance alone — a `version` bump or `last_updated` refresh with no other integrity change.
- An ordinary application-code change touching no Markdown and no documentation contract.
- A prose-only edit to repository Markdown outside the vault that touches no wiki-link, no governed document, and no sync mechanism — this skill does not own all Markdown merely because it is documentation.
- Wiki-link syntax quoted as an example inside inline code or a code fence (as in the skill wrappers themselves) — illustrative text, not a link.
- A change to CI workflow configuration, including the `governance docs (sync check)` job in `.github/workflows/ci.yml` — [[Code Reviewer]]'s CI trigger and the project owner own that surface; this skill relies on the gate but never reviews the pipeline.

## Check Sequence

1. **Frontmatter completeness** — every note has `title, category, status, version, last_updated, tags`; content notes converted from source PDFs also carry `source_pdf` (per [[README]]).
2. **Wiki-link resolution — repository-wide** — every `[[target]]` or `[[target|alias]]` in any repository Markdown file resolves to an existing note title or a frontmatter alias; folder-reference links (e.g. `[[13 Templates]]`) are recognized as valid, not falsely flagged, and link syntax inside inline code or code fences is illustrative, not a link. On a vault move, rename, or delete, sweep the whole repository for inbound links, not just the vault. A broken link inside a generated target is fixed in its canonical source and regenerated, never in the target.
3. **MOC/index membership** — a new note is linked from at least one MOC and appears in the relevant index(es) ([[Global Index]], [[Alphabetical Index]], [[Category Index]], and [[Documentation Index]] if it's vault infrastructure). After a wiki-link deletion, move, rename, or note removal, every affected surviving note must still be reachable from an appropriate MOC and retain its required index membership — deleting the last MOC/index link to a note orphans it as effectively as never adding one. Intentional retirement follows check 5's archived/superseded rules instead of this one. Where the right MOC for a stranded note is a categorization judgment, escalate per Escalation rather than inferring one. A note reachable only from its own folder listing is effectively lost (§19, README "How to Maintain the Vault").
4. **Navigation block** — every note ends with a Navigation block; Previous/Next reflect actual reading order within its series, Parent points to its real MOC, Related Notes are still valid links.
5. **Status accuracy** — a note describing a settled decision is `stable`, not left at `draft`; a superseded note is `archived` and physically in `99 Archive/` if appropriate.
6. **Governed-document parity** — `scripts/sync-governance-docs.config.json` is authoritative for both the complete list of canonical-source → generated-target pairs and the transformation each target must match (frontmatter stripping, callout stripping, stripping from a configured heading, and the source/target paths themselves). Every configured target must match the output of that configured transformation as produced by the live sync mechanism — the skill never manually infers or hardcodes which differences between source and target are permitted. Verify with `./scripts/sync-governance-docs.sh --check` (macOS/Linux/Git Bash) or `.\scripts\sync-governance-docs.ps1 -Check` (Windows PowerShell); the deprecated `sync-claude-md.*` shims merely delegate here and are never the instruction to give. Generated targets are never edited directly — port substantive content into the canonical source and regenerate. As of this version the configured pairs are `ProjectOne Vault/00 Governance/CLAUDE.md` → root `CLAUDE.md` and `ProjectOne Vault/00 Governance/AGENTS.md` → root `AGENTS.md`; these are current examples only — the config, not this note, is the list of record. This check is verification, not enforcement: the required `governance docs (sync check)` CI gate remains the authority, and a PASS here never substitutes for it.
7. **No duplicate canonical content** — a concept documented once is linked to elsewhere, never re-explained in a second note (§19, README "One Template Library, Not Two" as the precedent case).
8. **Build Plan status integrity** — two verifications, both mechanical. *Representation agreement:* for every step with a live row in the [[Build Plan]] index, the step note's `step_status` frontmatter, the status value opening its `**Status:**` line (the line may elaborate after the value — "Done — merged as ..." is the established shape), and the index row's Status cell all agree; a superseded note carries `step_status: Superseded` and no live row. *Lifecycle closure:* where completion or merge evidence exists — a merged Pull Request or squash commit on `main` referencing the step, a Step Completion Record, or the step presented as complete — the recorded status must reflect the completed state [[Execution Protocol]] requires; representations agreeing on a stale value is the defect, not a pass. This check never invents the true status: when evidence and recorded state conflict or remain ambiguous, it reports the evidence and escalates to the owner. Both defect classes are recorded history, not hypothesis: STEP-29 and STEP-30 merged while note and index still *agreed* on `In Progress`, and each needed an owner-decided closure commit afterwards (PRs #24 and #27).

## Outputs

A findings list grouped by file, each with the specific gap (missing frontmatter field, broken link, missing index entry, stale status) and the exact fix. For a renumbering or bulk-move operation, additionally outputs a before/after file-count reconciliation (as was done for the Phase 6 renumbering: 111 → 108 notes, accounting for 3 deliberately deleted pointer notes, 46 PDFs unchanged) so scale of the operation is verifiable at a glance.

## Escalation

Stops and asks (per §33–34) when:

- A note appears orphaned but it's unclear which MOC it should belong to (a genuine categorization judgment, not a mechanical fix).
- Two notes appear to duplicate the same content and it's unclear which is canonical.
- A structural change (renumbering, consolidation) is large enough that Documentation Keeper should propose the mapping before executing it, per the same standard CLAUDE.md applies to any high-blast-radius change — even though the change itself is reversible, a large mechanical pass is cheaper to get right once than to redo.
- Build Plan completion/merge evidence and the recorded status conflict, or the true state is not decidable from the note, the index, and the merge history alone — report the evidence and every recorded value, and ask; never pick one (the STEP-29 and STEP-30 closures were owner decisions for exactly this reason).
- A generated target was edited directly with substantive new content — confirm porting it into the canonical source before regenerating, so regeneration discards nothing the owner meant to keep.

## Related Skills

- [[Code Reviewer]] — hands off the "documentation currency" flag (its own check step 6) to Documentation Keeper for actual remediation.
- [[Code Reviewer]] — leads on CI workflow configuration, including the `governance docs (sync check)` job; Documentation Keeper relies on that required check as the enforcing gate, never reviews the pipeline, and never substitutes for it.
- All other skills — any skill whose check sequence references a CLAUDE.md section or vault note relies on Documentation Keeper to keep those references valid.

---

## Navigation

- **Previous:** [[AI Systems Engineer]]
- **Next:** —
- **Parent:** [[SKILLS]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[README]] · [[Documentation Index]]
