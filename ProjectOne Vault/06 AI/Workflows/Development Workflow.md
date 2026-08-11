---
title: Development Workflow
category: AI/Workflows
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, workflow, engineering]
aliases: []
---

# Development Workflow

How Claude actually does day-to-day engineering work inside ProjectOne — which tool handles which class of task, and how the validated AI operating capabilities fit together per the Feature Development Workflow in CLAUDE.md §30. For the overall task lifecycle (receive → plan → implement → report), see [[Task Workflow]] in [[01 Claude OS]] — that note governs the process; this one governs tool choice within it.

## Tool Selection by Task Type

| Task | Tool | Notes |
|---|---|---|
| Shell commands, git, npm/node, scripts | [[MCP/Terminal|Terminal]] | Built-in harness capability, not an MCP server. No delete/deploy actions without confirmation per the session's action-category rules. |
| Reading/writing/editing project or vault files | [[MCP/Filesystem|Filesystem]] | Official `@modelcontextprotocol/server-filesystem`. **Never use `move_file` onto a path that might already exist** — it silently overwrites (validated bug, see the note). |
| Deleting files or directories | [[MCP/Terminal|Terminal]] | Filesystem MCP has no delete capability at all — this is the only path for deletion. |
| Browser/UI validation of frontend changes | [[MCP/Playwright|Playwright]] | Harness-native Browser pane. Exploratory/manual validation only — not a substitute for a real `@playwright/test` CI suite once one exists. |
| Native desktop app or cross-app automation | [[MCP/Computer Use|Computer Use]] | Fallback only — prefer the dedicated tool for browsers (Playwright) and terminals (Terminal) where one exists; Computer Use's own tiering enforces this. |
| GitHub repository, PR, and issue operations | [[MCP/GitHub|GitHub]] | Official `github` MCP server, now against a live remote. `gh` CLI is not installed — use these tools for remote operations. Opening a PR is how every change reaches `main` ([[Branch and Pull Request Workflow]]); merging is the owner's decision, never Claude's. |
| Database operations | [[MCP/Supabase|Supabase]] | Not yet validated — reserved until ProjectOne has a database layer. |
| Deployment operations | [[MCP/Vercel|Vercel]] | Not yet validated — reserved until ProjectOne has a deployable frontend. |

## Applying CLAUDE.md §30 (Feature Development Workflow)

1. Confirm the feature survives the Product Bible filter.
2. Check it against [[Roadmap]] and existing feature docs.
3. Apply the Decision Framework (§6) before writing code — read [[Engineering Handbook MOC]] and the relevant architecture MOC first.
4. Implement using [[MCP/Filesystem|Filesystem]] for file work and [[MCP/Terminal|Terminal]] for builds/tests, following the layer standards in Engineering Handbook Chapters 3–9.
5. Validate UI changes in a real browser via [[MCP/Playwright|Playwright]] before considering frontend work complete.
6. Update documentation in the same change (§19) — this is [[Skills/Documentation Keeper|Documentation Keeper]]'s domain.
7. Confirm Definition of Done (§22) before considering the work complete.

## Validation Discipline

Every AI operating capability catalogued in [[AI Index]] is validated the same way before being trusted for real work:

1. Confirm installation status honestly — built-in harness capability vs. installed MCP server vs. not yet installed.
2. Run real operations against a disposable scratch directory or environment, never against ProjectOne's actual files or a live remote, unless the task explicitly requires it and is confirmed first.
3. Verify claimed success independently (read back file contents, inspect DOM state, check exit codes) rather than trusting a tool's own "success" response.
4. Record bugs, limitations, and workarounds in the capability's own note — see [[MCP/Filesystem|Filesystem]] and [[MCP/Playwright|Playwright]] for the standard this documentation follows.
5. Clean up every artifact created during validation and confirm cleanup, before reporting the work as done.

## Related Skills

Skills relevant to code produced through this workflow: [[Skills/Code Reviewer|Code Reviewer]] (review checklist), [[Skills/Architecture Reviewer|Architecture Reviewer]] (new dependencies/frameworks), [[Skills/Documentation Keeper|Documentation Keeper]] (keeping this vault in sync as capabilities change).

---

## Navigation

- **Previous:** [[Workflows/AI Workflow|AI Workflow]]
- **Next:** [[Workflows/Documentation Workflow|Documentation Workflow]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[AI Index]] · [[Engineering Handbook MOC]] · [[CLAUDE|CLAUDE.md]]
