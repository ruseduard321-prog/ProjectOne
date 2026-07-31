---
title: AI Index
category: Index
status: stable
version: "1.3"
last_updated: 2026-07-31
tags: [index, ai, documentation]
aliases: ["05 AI Index", "AI Section Index"]
---

# AI Index

Entry point for ProjectOne's AI operating documentation — governance, skills, MCP integrations, agents, prompts, and workflows that govern how Claude (and any future AI tooling) works inside this repository.

> [!info] Not to be confused with [[AI MOC]]
> [[AI MOC]] (in `03 Project Bible/02 AI Systems`) is the **product** map of content — AI Architecture, Agent Architecture, Memory System, AI Providers, Workflow Engine as ProjectOne *features*. This index is the **operating** map of content — how AI actually does the work of building the product. Both link to each other; neither replaces the other.

## Governance

- [[CLAUDE|CLAUDE.md]] — the constitution, lives in [[00 Governance]]. Also referenced here via [[06 AI/CLAUDE (pointer)|pointer note]].

## Skills

- [[SKILLS]] — overview and index of all specialized AI skills
- [[Skill Contract]] — the shared execution model every skill follows (dual-layer vault spec + `.claude/skills/` runtime wrapper, Critical/Advisory classification)

**Active — all ten skills, defined with runtime wrappers:**

- Critical: [[Skills/Security Reviewer|Security Reviewer]] · [[Skills/Database Engineer|Database Engineer]] · [[Skills/Architecture Reviewer|Architecture Reviewer]]
- Advisory: [[Skills/Code Reviewer|Code Reviewer]] · [[Skills/AI Systems Engineer|AI Systems Engineer]] · [[Skills/Documentation Keeper|Documentation Keeper]] · [[Skills/Full Stack Engineer|Full Stack Engineer]] · [[Skills/Bug Investigator|Bug Investigator]] · [[Skills/Performance Reviewer|Performance Reviewer]] · [[Skills/Release Manager|Release Manager]]

**Runtime wrappers:** `.claude/skills/security-reviewer/`, `.claude/skills/database-engineer/`, `.claude/skills/architecture-reviewer/`, `.claude/skills/code-reviewer/`, `.claude/skills/ai-systems-engineer/`, `.claude/skills/documentation-keeper/`, `.claude/skills/full-stack-engineer/`, `.claude/skills/bug-investigator/`, `.claude/skills/performance-reviewer/`, `.claude/skills/release-manager/` — auto-trigger in Claude Code sessions; each `SKILL.md` points back to its vault spec as source of truth.

## MCP (Model Context Protocol Integrations)

This section is also the MCP Index — the single catalog of every MCP server and harness-native AI operating capability. There is no separate "MCP Index" note; see the README's "one canonical location" principle.

**Validated:**

- [[MCP/GitHub|GitHub]] — official `github` MCP server, user-scoped registration, PAT-authenticated (confirmed live against the GitHub API). Tool manifest (24 tools) confirmed loadable in a fresh session. No real create/read/update operation against an actual repository has been exercised yet (no live git remote in this repo).
- [[MCP/Filesystem|Filesystem]] — official `@modelcontextprotocol/server-filesystem`, configured in `.mcp.json`. Fully validated; one high-severity bug found (`move_file` silently overwrites an existing destination — see note).
- [[MCP/Terminal|Terminal]] — **not an MCP server**, built-in Claude Code harness capability (Bash/PowerShell). Fully validated.
- [[MCP/Playwright|Playwright]] — harness-native Browser pane, Playwright-backed (Chromium only; no project npm dependency). Fully validated for exploratory use; several gaps found (no JS error capture, no file upload, mobile emulation is viewport-only).
- [[MCP/Computer Use|Computer Use]] — **not an MCP server**, built-in harness capability for native desktop automation, tiered by application category. Fully validated against a real native app (Notepad). **A real credential-exposure incident occurred during validation — see the note's Security Incident section before using this capability again.**

**Not yet validated:**

- [[MCP/Supabase|Supabase]] · [[MCP/Vercel|Vercel]] — reserved for the database and deployment layers respectively; stubs until ProjectOne has a database/deployment target to validate against.

> [!warning] Unresolved security finding
> Validating [[MCP/Computer Use|Computer Use]] surfaced two live secrets (a GitHub PAT and an Anthropic API key) in plaintext on-screen, captured in a screenshot. A separate, lower-severity incident during [[MCP/GitHub|GitHub]] installation echoed a PAT into a session transcript. Rotation status for both is **unconfirmed** as of 2026-07-31 — verify and rotate if not already done.

## Agents

- [[Agents/Agents Index|Agents Index]]

## Prompts

All prompts live here, under `06 AI/Prompts/` — there is no separate prompt library elsewhere in the vault.

- [[Prompts/Prompt Standards|Prompt Standards]] — operating rules for every prompt
- [[Prompt Template]] (in [[13 Templates]]) — the template used to create a new prompt note in this folder

## Workflows

- [[Workflows/Development Workflow|Development Workflow]] — **stable**, documents tool selection across all validated AI operating capabilities
- [[Workflows/AI Workflow|AI Workflow]] · [[Workflows/Documentation Workflow|Documentation Workflow]] · [[Workflows/Release Workflow|Release Workflow]] — still stubs

## Templates

AI-specific templates live alongside every other vault template in [[13 Templates]] — there is no separate AI template folder, to avoid the two drifting apart.

- [[Skill Template]] — for defining a new Skill in this section
- [[ADR Template]] · [[Workflow Template]] · [[Prompt Template]] — shared with the rest of the vault

---

## Navigation

- **Parent:** [[Home]]
- **Related Notes:** [[CLAUDE|CLAUDE.md]] · [[AI MOC]] · [[Engineering Handbook MOC]] · [[13 Templates]]
