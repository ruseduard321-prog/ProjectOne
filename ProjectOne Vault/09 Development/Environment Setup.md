---
title: Environment Setup
category: Development
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [engineering, documentation, ai, mcp]
aliases: ["Local Development Setup", "AI Tooling Setup"]
---

# Environment Setup

The current state of ProjectOne's local development environment and AI operating capabilities, as verified by direct validation rather than assumed from configuration files alone. This note answers "what's actually available and working right now" — for the standards each capability must follow, see [[AI Index]] and the individual [[MCP/GitHub|MCP]] notes.

## Machine Environment (as validated)

- **OS:** Windows 11, native (not WSL)
- **Shell:** PowerShell (primary, used as the harness's default shell tool since Git for Windows is not installed); Bash also available via the harness's bundled MSYS environment
- **Node.js:** v24.18.0
- **npm:** 11.16.0
- **Git:** available for local operations; `gh` CLI is **not installed** — GitHub operations go through the [[MCP/GitHub|GitHub MCP]], not the CLI
- **Repository state:** ProjectOne is **not currently under git version control** locally — `git status`/`log`/`branch` all correctly report "not a git repository." This affects what [[MCP/GitHub|GitHub MCP]] can be validated against today.

## AI Operating Capabilities — Status Summary

See [[AI Index]] for the full catalog. Summary as of this validation pass:

| Capability | Type | Status |
|---|---|---|
| [[MCP/Filesystem|Filesystem]] | Official MCP server (`@modelcontextprotocol/server-filesystem`) | Configured in `.mcp.json`, fully validated |
| [[MCP/Terminal|Terminal]] | Built-in harness capability | No installation needed, fully validated |
| [[MCP/Playwright|Playwright]] | Harness-native, Playwright-backed | No installation needed, fully validated (Chromium only) |
| [[MCP/Computer Use|Computer Use]] | Built-in harness capability | No installation needed, fully validated against a real native app — **see security incident in the note** |
| [[MCP/GitHub|GitHub]] | Official MCP server | Configured (outside project `.mcp.json`); PAT-authenticated and tool manifest confirmed loadable; no real repository operation exercised yet |
| [[MCP/Supabase|Supabase]] | MCP server (reserved) | Not yet installed or validated — no database layer exists yet |
| [[MCP/Vercel|Vercel]] | MCP server (reserved) | Not yet installed or validated — no deployable frontend exists yet |

## Project-Level MCP Configuration

`.mcp.json` (project root) currently declares only the Filesystem server:

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:\\ProjectOne ProjectBible"]
    }
  }
}
```

GitHub is available in-session but is **not** declared here — it is configured at a level above the project. Terminal, Playwright, and Computer Use are harness-native and never appear in `.mcp.json` at all, since they are not MCP servers.

## Setting Up a New Machine

1. Install Node.js and npm (validated against v24.18.0 / 11.16.0 — the exact versions are not a hard requirement, but this is the last known-good baseline).
2. Ensure `.mcp.json` is present at the project root — the Filesystem server bootstraps automatically via `npx` on first use, no manual install step required.
3. Terminal, Playwright (Chromium), and Computer Use are available immediately with no setup — they ship with the Claude Code harness itself.
4. If GitHub operations are needed, confirm the GitHub MCP server is configured at the appropriate level (user/global config) — this is outside `.mcp.json` and outside this repository's version control.
5. Initialize git version control in the project root before relying on any GitHub MCP operation that presupposes a repository (branch creation, PR creation, push).
6. Firefox and WebKit browser binaries are **not** installed by default (Chromium only) — install deliberately with `npx playwright install firefox webkit` only if cross-browser manual validation becomes necessary; this is a real download/disk-write action, not a no-op.

## Known Gaps

- No Supabase or Vercel MCP configuration exists yet — expected, since ProjectOne has no database or deployment target yet.
- `@playwright/test` is not installed as a project dependency — the harness's Playwright capability is validated for exploratory/manual use only, not automated CI test coverage. See [[MCP/Playwright|Playwright]] Recommendations.
- No real create/read/update operation has been exercised against an actual GitHub repository yet — see [[MCP/GitHub|GitHub]].
- No `08 ADR/` entries exist yet recording these tooling decisions as formally accepted architecture — see [[08 ADR]].

## Unresolved Security Finding

Validating [[MCP/Computer Use|Computer Use]] surfaced two live secrets in plaintext on-screen (a GitHub PAT and an Anthropic API key), captured in a screenshot taken during the validation run. A second, separate incident during [[MCP/GitHub|GitHub]] installation echoed a PAT into a session transcript via `claude mcp get github`. **Rotation status for both is unconfirmed as of 2026-07-31.** Verify and rotate both credentials if this has not already been done — see the Security Incident section in [[MCP/Computer Use|Computer Use]] for full detail.

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[AI Index]] · [[Workflows/Development Workflow|Development Workflow]] · [[MCP/GitHub|GitHub]] · [[MCP/Filesystem|Filesystem]] · [[MCP/Terminal|Terminal]] · [[MCP/Playwright|Playwright]] · [[MCP/Computer Use|Computer Use]]
