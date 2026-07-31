---
title: README
category: Meta
status: stable
version: "1.2"
last_updated: 2026-07-31
tags: [documentation]
---

# ProjectOne Vault — README

This vault is the organized, cross-linked Obsidian knowledge base for ProjectOne. It was built by converting every source PDF (Project Bible, Engineering Handbook, Design System) into Markdown, then connecting the result with Maps of Content, wiki-links, tags and navigation blocks. **No technical content was expanded, rewritten, simplified or reinterpreted during conversion** — every note preserves the source document's meaning, structure and wording. The original PDFs remain the official archived source of truth, stored in [[12 Assets/PDF]].

## Folder Structure

| Folder | Purpose |
|---|---|
| `00 Governance` | **The ProjectOne Constitution** — [[CLAUDE\|CLAUDE.md]]. Binding operating rules for how Claude thinks, decides, and writes code. Numbered first: governance outranks every other folder. |
| `01 Claude OS` | **The operating manual for Claude itself** — [[Start Here]], [[Documentation Discovery]], [[Reading Priority]], [[Task Workflow]]. Claude reads this folder before starting any ProjectOne task; it governs *how* the rest of the vault gets read and used, not the product itself. Numbered second: read right after governance, before anything product-specific. |
| `02 Home` | Entry point: [[Home]] dashboard and the index notes |
| `03 Project Bible` | The product specification — Foundations, Features, AI Systems, Tech Architecture, Delivery & Trust |
| `04 Engineering Handbook` | **Canonical** engineering standards, Chapters 1–11 |
| `05 Architecture` | Cross-cutting architecture MOC tying together AI/backend/frontend/database/infra |
| `06 AI` | AI **operating** documentation — Skills, MCP integrations, Agents, Prompts, Workflows. See [[AI Index]]. AI-specific templates live in `13 Templates/` alongside every other template, not duplicated here. |
| `07 Features` | Feature-level documentation and the Design System |
| `08 ADR` | Architecture Decision Records (empty — populate using [[ADR Template]]) |
| `09 Development` | Engineering process notes: bugs, sprints, releases |
| `10 Research` | Research notes, user research, meeting notes |
| `11 Decisions` | Standalone product/architecture decisions outside the ADR log |
| `12 Assets` | Archived source PDFs (`12 Assets/PDF/`) and any future binary assets |
| `13 Templates` | Reusable note templates for every recurring content type, including AI-specific ones (e.g. Skill Template) |
| `99 Archive` | Historical/superseded documents — currently [[Technical Documentation Master]]. Fixed at `99` regardless of how many numbered folders precede it, so it always reads as "the attic." |

Numbering is sequential with no gaps and no lettered workarounds (`04a`, etc.) — every folder has a plain integer prefix, chosen so the sequence still makes sense after years of growth: governance and Claude's own operating manual first (`00`–`01`), orientation next (`02`), product and engineering knowledge next (`03`–`05`), how-the-work-gets-done next (`06`–`07`), process and provenance next (`08`–`12`), archive fixed at `99`. This was renumbered on 2026-07-31 to insert `01 Claude OS`, shifting every folder from the old `01`–`12` up by one — see [[Environment Setup]] or Claude OS's own notes for context if a stale reference to the old numbering surfaces anywhere.

**Reading `01 Claude OS/Start Here.md` is not just a convention — it is step 0 of [[CLAUDE|CLAUDE.md]] §6 (Decision Framework), binding on every task.** The vault is ProjectOne's primary knowledge source; Claude OS is the procedure for using it without reading the whole thing every time.

## Canonical vs. Historical Documentation

The **Engineering Handbook** (`04 Engineering Handbook/`) is the canonical source of engineering standards. **[[CLAUDE|CLAUDE.md]]** (`00 Governance/`) operationalizes both the Engineering Handbook and the Project Bible into binding day-to-day behavior — see its own source-of-truth hierarchy at the top of the document. The **Technical Documentation Master** (`99 Archive/`) proposed an earlier `100–199` numbering scheme that was never adopted — it is kept for historical reference only. If the Engineering Handbook and the Master ever appear to conflict, the Engineering Handbook wins; if CLAUDE.md and either appear to conflict, CLAUDE.md's own stated hierarchy resolves it.

## One Template Library, Not Two

Every template in the vault — including AI-specific ones like Skill Template — lives in `13 Templates/`. There is no separate template folder inside `06 AI/`, and no pointer/duplicate notes forwarding from one to the other. This was a deliberate correction: an earlier revision of this vault kept AI templates in their own folder with pointer notes back to the canonical copies, which is exactly the kind of split that drifts out of sync over time. One canonical location per template, referenced from wherever it's needed.

## Naming Conventions

- **Note titles** use the plain subject name (e.g. `Database Architecture.md`), not the original file's numeric prefix. The numeric prefix (e.g. `31`) is preserved in the note's `aliases` frontmatter so the old name still resolves in search and links.
- **Engineering Handbook chapters** are named `Chapter NN - Title.md` to preserve reading order in the file browser.
- **MOCs** are named `<Topic> MOC.md`.
- **Templates** are named `<Type> Template.md`.
- **Indexes** live in `02 Home/` and are named `<Scope> Index.md`.

## Frontmatter

Every note carries YAML frontmatter:

```yaml
---
title:          # display title
category:       # e.g. Project Bible/Foundations, Engineering Handbook, MOC, Index, Archive
status:         # draft | stable | archived | proposed | open | planned
version:        # matches the source document version (0.1 or 1.0)
last_updated:   # ISO date
tags:           # from the vault's controlled tag list, see below
aliases:        # alternate names, including the original numbered filename
source_pdf:     # wiki-link to the archived original PDF (content notes only)
---
```

## How MOCs Work

A Map of Content (MOC) is a curated hub note that links related notes together with context, rather than a folder listing. There are 12 MOCs, one per major domain (Project Bible, Engineering Handbook, Architecture, Features, Security, AI, Backend, Frontend, Database, Development, Research, Design), plus [[AI Index]] which serves the same role for AI **operating** documentation (Skills, MCP, Agents, Prompts, Workflows — distinct from the AI **product** documentation the AI MOC covers). Start from [[Home]], drill into a MOC, then into individual notes. MOCs cross-link each other under **Related MOCs** so the graph reflects how the domains actually relate — not just folder adjacency.

## How Internal Linking Works

Every content note links to related notes in two places:

1. **Inline `See also:` links** where a source document explicitly referenced another concept (e.g. [[AI Chat]] references [[Memory System]] because the original text describes the AI accessing project memory).
2. **A `Navigation` block at the end of every note** with `Previous`, `Next` (reading order within its series), `Parent` (its MOC), and `Related Notes`.

Because links point to note titles, Obsidian's Graph View will cluster notes by actual subject-matter relationships (AI systems, security, architecture) rather than by folder — this is intentional, so the graph mirrors ProjectOne's real architecture.

## Tags

A controlled tag vocabulary is used consistently:

`#project-bible` `#engineering` `#architecture` `#backend` `#frontend` `#database` `#ai` `#security` `#testing` `#design` `#feature` `#deployment` `#documentation` `#prompt` `#moc` `#index` `#archive` `#governance` `#mcp` `#workflow`

Use the Tag pane or `Category Index` to browse by tag/category.

## How to Add New Documentation

1. Pick the correct folder from the table above.
2. Copy the closest-matching template from `13 Templates/` (or an existing note if no template fits).
3. Fill in frontmatter — set `status: draft`, correct `category` and `tags`.
4. Write content, linking to related notes with double-bracket wiki-links as you go (e.g. `[[Database Architecture]]`).
5. Add a `Navigation` block at the end (`Previous`, `Next`, `Parent`, `Related Notes`).
6. Add the new note to the relevant MOC(s) and to `Global Index` / `Alphabetical Index` / `Category Index`.
7. If the note documents architecture, add or update a Mermaid diagram rather than prose-only descriptions where practical.

## How to Use Templates

Open a template in `13 Templates/`, use Obsidian's **Copy file** (or the Templater/Templates core plugin if enabled) to instantiate it into the correct folder, then replace every `{{placeholder}}`. Templates already include correct frontmatter shape and a Navigation stub — don't remove those fields, just fill them in.

## How to Maintain the Vault

- **Never edit an archived PDF's meaning when converting** — if you find a transcription gap, fix the Markdown to match the PDF, not the other way around.
- **Keep the Engineering Handbook canonical.** If a new engineering decision is made, it belongs in a Handbook chapter (or a new ADR in `08 ADR/`), not in the archived Master doc.
- **Update indexes when adding notes.** A note that exists only in its folder and isn't linked from any MOC or index is effectively lost — always link it from at least one MOC.
- **Prefer linking over duplicating.** If a concept is already documented, link to it with a wiki-link instead of re-explaining it.
- **Keep `status` accurate.** Promote `draft` → `stable` once a document reflects a settled decision; mark superseded documents `archived` and move them to `99 Archive/`.

---

## Navigation

- **Parent:** [[Home]]
- **Related Notes:** [[Documentation Index]] · [[Engineering Handbook MOC]]
