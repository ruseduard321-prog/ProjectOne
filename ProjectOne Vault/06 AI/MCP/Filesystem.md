---
title: Filesystem
category: AI/MCP
status: stable
version: "1.0"
last_updated: 2026-07-31
tags: [ai, mcp]
aliases: ["Filesystem MCP"]
---

# Filesystem MCP

## Purpose

Gives Claude sandboxed, tool-mediated access to the local filesystem — read, write, edit, move, search, and directory listing — scoped to explicitly allowed directories rather than raw shell access. This is the primary way Claude reads and edits ProjectOne source files, vault notes, and configuration outside of the harness's own built-in file tools.

## Installation Status

**Installed and configured.** Runs as a stdio MCP server launched via `npx`, defined in the project's `.mcp.json`:

```json
"filesystem": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "D:\\ProjectOne ProjectBible"]
}
```

This is the **official** `@modelcontextprotocol/server-filesystem` package — the reference implementation maintained under the Model Context Protocol project, not a community fork. Allowed-directory scope is currently the full project root; no subdirectory restrictions are configured.

## Validation Status

**Validated 2026-07-30.** 13 tools exercised against a disposable `_mcp_validation/` scratch folder inside the project root, fully cleaned up afterward. Result summary:

| Capability | Result |
|---|---|
| Read files (single, multi, media) | Pass |
| Create files | Pass |
| Edit files (dry-run + real) | Pass |
| Rename files | Pass |
| Move files (cross-directory) | Pass |
| Delete files/directories | **Not available — no delete tool exists in this server** |
| Create directories | Pass, with a caveat (see Bugs) |
| Search files | Pass, with a caveat (see Bugs) |
| Read large/nested directory trees | Pass |

## Architecture

Runs as a separate Node process (`npx @modelcontextprotocol/server-filesystem`) communicating with Claude Code over stdio, per the standard MCP client/server model. It is stateless per call and enforces its allowed-directories allowlist server-side — Claude cannot request a path outside `D:\ProjectOne ProjectBible` regardless of what a tool call asks for.

## How It Is Used Inside ProjectOne

This is the default mechanism for any file operation Claude performs against the ProjectOne repository or vault: reading source/config/vault files, writing new files, editing existing ones, and locating files by glob pattern. It complements (does not replace) the harness's built-in Read/Write/Edit/Glob/Grep tools, which operate over the same filesystem through a different path.

## Best Practices

- Always verify a destination path is intentionally empty before calling `move_file` — see the overwrite bug below. Check first with `get_file_info` or `list_directory` if there's any doubt.
- Use `**/*.ext` glob syntax for `search_files`, not bare `*.ext` or substrings — the simpler forms silently return no matches even against real files.
- Build nested directories top-down (`mkdir A`, then `mkdir A/B`), not in one call, since intermediate parents are not auto-created.
- For deletion, fall back to the harness's Bash/PowerShell tools — this server has no delete capability at all.

## Limitations

- **No delete/remove tool of any kind.** Neither files nor directories can be deleted through this server.
- `search_files` requires exact glob syntax; the tool's own description overstates how forgiving pattern matching is.
- `create_directory`'s description claims it "can create multiple nested directories in one operation" — it cannot; each intermediate parent must already exist.

## Bugs Discovered During Validation

- **Data-loss bug in `move_file` (high severity).** The tool's description explicitly states "If the destination exists, the operation will fail." In practice it silently **overwrites** the destination file with no error and no confirmation, destroying the original destination content. Confirmed by moving a file onto an existing target and reading back the overwritten result.

## Workarounds

- Treat every `move_file` call as a silent overwrite; manually check the destination doesn't already exist (or doesn't hold anything you need) before calling it.
- Use the harness's Bash/PowerShell `rm`/`Remove-Item` for any deletion need, since this server cannot delete.
- Always use the full `**/*.ext` glob form for search, never the shorthand the tool description implies works.

## Recommendations

- Report the `move_file` overwrite behavior upstream to the `@modelcontextprotocol/server-filesystem` maintainers — it's a documentation/implementation mismatch with real data-loss potential for any consumer trusting the documented contract.
- If deletion capability becomes a frequent need, prefer routing it through the harness's own Bash/PowerShell tools rather than requesting a scope expansion of this server — keeps the MCP surface narrow and auditable.

## Future Improvements

- Consider narrowing the allowed-directories scope below the full project root if/when the repository grows subprojects that shouldn't be mutually visible to every Claude session.
- Re-validate after any version bump of `@modelcontextprotocol/server-filesystem`, since the overwrite bug may be fixed upstream without notice.

---

## Navigation

- **Previous:** [[MCP/GitHub|GitHub]]
- **Next:** [[MCP/Terminal|Terminal]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[MCP/Terminal|Terminal]] · [[MCP/Playwright|Playwright]] · [[CLAUDE|CLAUDE.md]]
