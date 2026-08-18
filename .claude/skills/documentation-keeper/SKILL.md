---
name: documentation-keeper
description: Keeps the repository's documentation contracts consistent — vault frontmatter and note integrity, repository-wide wiki-link resolution, MOC/index membership, Navigation blocks, status accuracy, governed-document parity, and Build Plan status integrity. Triggers on any add/move/rename/delete or folder renumbering under "ProjectOne Vault/"; on a wiki-link added, modified, or deleted in any repository Markdown file; on required frontmatter fields added/removed, title/aliases/category/status changed, a Navigation block added/modified/removed, or a template convention changed in "ProjectOne Vault/13 Templates/"; on a canonical source or generated target defined in scripts/sync-governance-docs.config.json changing (a direct target edit is itself the finding), or on scripts/sync-governance-docs.sh, scripts/sync-governance-docs.ps1, or that config changing; on a Build Plan step status changing in the note or index, or a step presented as complete or merged without either changing; and on explicit request. Not triggered by body-prose edits, routine version/last_updated bumps, application-code changes, wiki-link syntax in code spans/fences, or CI workflow edits. Advisory — recommends only.
classification: advisory
---

# Documentation Keeper

Source of truth: `ProjectOne Vault/06 AI/Skills/Documentation Keeper.md` (reasoning, scope, escalation rules). This file only operationalizes it — do not restate the *why* here; update the vault note instead and keep this in sync.

Shared execution model: `ProjectOne Vault/06 AI/Skill Contract.md`.

## Trigger Conditions

Fires on changes to the **documentation contracts this skill guards** — vault structure and note integrity, link integrity, governed-document parity, build-plan status integrity. A Markdown file merely being edited is never sufficient on its own.

**Vault file operations**
- File added, moved, renamed, or deleted under `ProjectOne Vault/`. Moves, renames, and deletes require the repository-wide inbound-link sweep (check 2) — Markdown outside the vault links into it.
- A folder's structure or numbering changes under `ProjectOne Vault/`.

**Vault note integrity**
- A required frontmatter field added or removed, or `title`, `aliases`, `category`, or note `status` changed. Routine `version`/`last_updated` maintenance alone does not fire.
- A Navigation block added, modified, or removed.
- A template under `ProjectOne Vault/13 Templates/` changed in a way that alters the documented convention.

**Wiki-link changes, anywhere in the repository**
- A wiki-link added, modified, or deleted in any repository Markdown file — inside `ProjectOne Vault/` or outside it (`infrastructure/*.md`, `scripts/README.md` carry live links into the vault today).

**Governed-document surface**
- A canonical source listed in `scripts/sync-governance-docs.config.json` changes — the configured target must be regenerated in the same change.
- A generated target listed in that config is edited directly — the direct edit is itself the finding; fix by porting content to the canonical source and regenerating, never by adjusting the target.
- `scripts/sync-governance-docs.sh`, `scripts/sync-governance-docs.ps1`, or `scripts/sync-governance-docs.config.json` changes — including a config document entry added or removed. Script code quality → `code-reviewer`; this skill verifies the parity contract and the documentation describing it.

**Build Plan status integrity**
- A step's status changes in the step note (`step_status` frontmatter or `**Status:**` line under `ProjectOne Vault/09 Development/Build Plan/Steps/`) or in the `Build Plan.md` index row — whether or not the other places changed too.
- A step is presented as complete, ready to close, or merged — a merged/referenced PR, a squash commit on `main`, a Step Completion Record, or the session presenting it as finished — even when no recorded status changed. Execution Protocol owns the rules; this skill verifies mechanically.

**Explicit request**
- User asks to check links, update indexes, or verify build-plan status consistency.

**Not a trigger:** a body-prose edit to an existing vault note changing no wiki-link, no required or identity frontmatter field, no Navigation block, and no status (canonical governance sources excepted — any change to them obligates regeneration); routine `version`/`last_updated` maintenance alone; ordinary application-code changes touching no documentation contract; prose-only edits to non-vault Markdown touching no wiki-link, governed document, or sync mechanism; wiki-link syntax quoted inside inline code or code fences (illustrative, not a link); CI workflow configuration including the `governance docs (sync check)` job (→ `code-reviewer` and the owner).

## Check Sequence

1. **Frontmatter completeness** — `title, category, status, version, last_updated, tags` present; `source_pdf` present on content notes converted from PDFs.
2. **Wiki-link resolution — repository-wide** — every `[[target]]` / `[[target|alias]]` in any repository Markdown file resolves to a note title or frontmatter alias; recognize legitimate folder-reference links rather than false-flagging them; link syntax inside inline code or code fences is illustrative, not a link. On a vault move/rename/delete, sweep the whole repository for inbound links, not just the vault. A broken link inside a generated target is fixed in its canonical source and regenerated, never in the target.
3. **MOC/index membership** — new notes are linked from at least one MOC and appear in `Global Index`, `Alphabetical Index`, `Category Index`, and `Documentation Index` if vault infrastructure. After a wiki-link deletion, move, rename, or note removal, every affected surviving note is still reachable from an appropriate MOC and still present in its required indexes — deleting the last inbound MOC/index link orphans a note. Intentional retirement follows check 5's archived/superseded rules; an ambiguous MOC choice escalates, never gets inferred.
4. **Navigation block** — every note ends with Previous/Next/Parent/Related Notes, all still valid.
5. **Status accuracy** — settled content is `stable`; superseded content is `archived` and physically in `99 Archive/` if appropriate.
6. **Governed-document parity** — `scripts/sync-governance-docs.config.json` is authoritative for both the complete list of source/target pairs and the transformation each target must match; every configured target must match the live sync mechanism's output — never a manually inferred or hardcoded set of permitted differences. Verify with `./scripts/sync-governance-docs.sh --check` or `.\scripts\sync-governance-docs.ps1 -Check`; never edit a generated target directly — port content to the canonical source and regenerate. Verification only: the required `governance docs (sync check)` CI gate remains the authority, and a PASS here never substitutes for it.
7. **No duplicate canonical content** — a concept is linked to, not re-explained, in a second note.
8. **Build Plan status integrity** — (a) *representation agreement:* for every step with a live index row, the note's `step_status` frontmatter, the status value opening its `**Status:**` line (elaboration after the value is the established shape), and the index row's Status cell agree; superseded notes carry `step_status: Superseded` and no live row. (b) *lifecycle closure:* where completion/merge evidence exists (a merged PR or squash commit on `main` referencing the step, a Step Completion Record, the step presented as complete), the recorded status must reflect the completed state Execution Protocol requires — representations agreeing on a stale value is the defect, not a pass. Never invents the true status: conflicting or ambiguous evidence is reported and escalated.

## Output Format

A findings list grouped by file: the specific gap and the exact fix. For a bulk move/renumbering, additionally output a before/after file-count reconciliation so the scale of the change is verifiable at a glance.

## Escalation

Stop and ask rather than deciding when:
- An orphaned note's correct MOC is a genuine categorization judgment, not a mechanical fix.
- Two notes appear to duplicate content and which is canonical is unclear.
- A structural change is large enough that the mapping should be proposed before executing it.
- Build Plan completion/merge evidence and the recorded status conflict, or the true state is not decidable from the note, the index, and the merge history — report the evidence and every recorded value, never pick one.
- A generated target was edited directly with substantive new content — confirm porting it into the canonical source before regenerating, so nothing the owner meant to keep is discarded.

## Handoff

- Receives the documentation-currency flag from `code-reviewer` (its check step 6) for remediation.
- CI workflow configuration, including the `governance docs (sync check)` job → `code-reviewer` skill and the project owner; that required check remains the enforcing gate — this skill's PASS never substitutes for it.
- Every other skill relies on this skill to keep the CLAUDE.md/vault references in their own check sequences valid.
