---
title: Terminal
category: AI/MCP
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, mcp]
aliases: ["Terminal MCP"]
---

# Terminal

## Purpose

Shell command execution — running builds, tests, git operations, scripts, and general command-line work on Claude's behalf inside ProjectOne.

## Installation Status

**Not an MCP server — nothing to install.** Terminal/shell execution is a **built-in capability of the Claude Code harness itself**, exposed as the native Bash tool (and PowerShell on native Windows). This was confirmed directly against the official documentation at `code.claude.com/docs/en/overview`: MCP is documented as the mechanism for connecting *external* tools (Jira, Slack, Google Drive, custom APIs) to Claude Code; shell execution is core harness functionality, configured through `permissions` allow/deny rules in `.claude/settings.json`, not through `claude mcp add`.

This note stays catalogued under `06 AI/MCP/` alongside true MCP servers for discoverability (it's part of the same "AI operating capability" surface a developer would look here for), but it is architecturally distinct: no server process, no `.mcp.json` entry, nothing to version or update independently of the Claude Code CLI itself.

On this project's environment (native Windows), Claude Code uses **PowerShell** as its shell tool because Git for Windows is not installed; Bash is also available (via the Git-for-Windows-style MSYS environment bundled with the harness) and was used interchangeably during validation.

## Validation Status

**Validated 2026-07-31.** Full checklist executed in a disposable OS temp scratch directory outside the project, cleaned up afterward.

| Capability | Bash | PowerShell |
|---|---|---|
| Basic shell commands | Pass | Pass |
| Create/remove directories | Pass | Pass |
| Create/copy/move/delete files | Pass | Pass |
| Git status/branch/log | Pass (scratch repo) | not re-tested (redundant) |
| Node/npm | Pass (v24.18.0 / 11.16.0) | Pass |
| Environment variables | Pass | Pass |
| Working directory handling | Pass, with a caveat (see Bugs) | Pass, with the same caveat |
| Script execution | Pass | not re-tested |
| Error handling (bad command, missing file, permission denied, custom exit code) | Pass — correct exit codes throughout | Pass — `try/catch` correctly caught errors |

## Architecture

Each Bash/PowerShell tool call runs as an independent process invocation from the harness — it is **not** a persistent interactive shell session. There is no MCP client/server hop involved; the harness executes the command directly and returns stdout/stderr/exit code to the model.

## How It Is Used Inside ProjectOne

The default mechanism for anything requiring shell execution: running `npm`/`node` commands, git operations, running test suites, invoking scripts, and general filesystem operations that the Filesystem MCP doesn't cover (notably: deletion, see [[MCP/Filesystem|Filesystem]]).

## Best Practices

- Never rely on working directory or environment variables persisting from a previous tool call — each call starts fresh at the project root. Use absolute paths or an explicit `cd`/`Set-Location` prefix within the same call as any command that depends on it.
- Set and consume environment variables within a single call (`export X=1 && command`), not across separate calls.
- Prefer PowerShell for native-Windows-specific operations and Bash for POSIX-style scripting; both share the same filesystem, so artifacts from one are visible to the other, but shell state is never shared between them.

## Limitations

- **Working directory does not persist between tool calls**, despite some tool descriptions implying otherwise ("the working directory persists between commands, but shell state does not"). In practice, both cwd and shell state reset every call in this environment.
- No true interactive/long-lived shell session — anything requiring stateful multi-step shell interaction (e.g., a REPL) needs to be scripted into a single call.

## Bugs Discovered During Validation

- Documentation/behavior mismatch on working-directory persistence (above) — not a functional defect, but worth knowing before assuming `cd` in one call affects a later one.

## Workarounds

- Use absolute paths, or explicit `cd "$DIR" && ...` / `Set-Location $DIR; ...` prefixes, in every call rather than relying on prior-call state.

## Recommendations

- No installation or configuration action needed — this capability is already correctly available and functioning.
- If tighter control over autopilot-vs-approval-required commands is wanted, define explicit `permissions.allow`/`deny` rules for Bash in `.claude/settings.json` (currently no project-level allowlist/denylist is configured, so default harness permission prompting applies).

## Future Improvements

- None identified. Re-validate only if the harness's shell-tool implementation changes (e.g., Git for Windows gets installed, switching the default shell tool from PowerShell to Bash on this machine).

---

## Navigation

- **Previous:** [[MCP/Filesystem|Filesystem]]
- **Next:** [[MCP/Playwright|Playwright]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[MCP/Computer Use|Computer Use]] · [[MCP/Filesystem|Filesystem]] · [[CLAUDE|CLAUDE.md]]
