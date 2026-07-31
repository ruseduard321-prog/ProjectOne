---
title: GitHub
category: AI/MCP
status: stable
version: "1.1"
last_updated: 2026-07-31
tags: [ai, mcp]
aliases: ["GitHub MCP"]
---

# GitHub MCP

## Purpose

Gives Claude direct access to GitHub — repositories, issues, pull requests, branches, commits, code search — without shelling out to `git`/`gh` for remote operations. Used for repository-hosted work once ProjectOne code lives on GitHub: creating branches, opening PRs, reviewing diffs, and issue/PR triage.

## Installation Status

**Installed and configured.** Official `github` MCP server (`@modelcontextprotocol/server-github`), registered via `claude mcp add`, launched as `npx -y @modelcontextprotocol/server-github`. Authentication is wired through `GITHUB_PERSONAL_ACCESS_TOKEN`, mapped from a pre-existing `GITHUB_PAT` environment variable (the official server does not read `GITHUB_PAT` by name — this mapping had to be set explicitly on re-registration after an initial attempt left the env var unwired).

Registration is at **user config scope** (`~/.claude.json`), not project scope — it does not appear in this project's `.mcp.json` (which only declares `filesystem`), consistent with what was documented previously, now confirmed as the deliberate original choice (this repository had no `.git` at install time, so project scope wasn't applicable).

This repository is **still not currently a git repository** (`git status` reports "not a git repository"), so no live GitHub remote is connected to ProjectOne itself.

## Validation Status

**Validated in two parts, across two separate sessions, both recovered from session history:**

1. **Credential and transport validation (confirmed working):**
   - `GITHUB_PAT` confirmed present in the environment (93 characters).
   - `claude mcp list` / `claude mcp get github` reported the server **✔ Connected**.
   - The server package was confirmed to run and start correctly on stdio (independent sanity check, not just config inspection).
   - **Live GitHub API call** (`GET /user`) made directly with the PAT, bypassing MCP transport, returned **200 OK**, authenticated as **`ruseduard321-prog`**. Confirmed as a fine-grained PAT (no classic OAuth-scopes header).

2. **Tool-surface validation (confirmed working, in a later session):**
   - A fresh session (started after registration) successfully loaded **24 `mcp__github__*` tools**: repo/file operations (`create_repository`, `fork_repository`, `get_file_contents`, `create_or_update_file`, `push_files`, `create_branch`, `list_commits`), issues (`create_issue`, `get_issue`, `list_issues`, `update_issue`, `add_issue_comment`), pull requests (`create_pull_request`, `get_pull_request`, `list_pull_requests`, `get_pull_request_files`, `get_pull_request_comments`, `get_pull_request_reviews`, `get_pull_request_status`, `create_pull_request_review`, `merge_pull_request`, `update_pull_request_branch`), and search (`search_code`, `search_issues`, `search_repositories`, `search_users`).

**Not validated:** no real create/read/update operation was executed against an actual GitHub repository or issue (e.g., no test repo created, no PR opened) — validation stopped at confirming the tools load and the credential authenticates. No live remote exists for ProjectOne to exercise these against yet.

## Architecture

Runs as a separate `npx`-launched MCP server process, communicating over stdio, authenticated via a fine-grained GitHub PAT passed as `GITHUB_PERSONAL_ACCESS_TOKEN`. Distinct from the `gh` CLI, which is not installed in this environment — all GitHub operations in this project go through the MCP tools, not shell-based `gh`/`git push`.

**Known session-loading behavior:** MCP server tool manifests are loaded at session startup. Registering or approving a server mid-session does **not** inject its tools into that already-running session — `claude mcp list` correctly reports the server as connected at the CLI/config level, but `ToolSearch` in the current conversation will not find its tools until a new session is started in the same project. This cost two full validation attempts before being correctly diagnosed and worked around by starting a fresh session.

## How It Is Used Inside ProjectOne

Once ProjectOne's code is pushed to a GitHub repository, this server becomes the mechanism for: opening pull requests, commenting on and reviewing PRs, creating/triaging issues, searching code and history across the repository, and branch management — governed by CLAUDE.md's Git Workflow (§20) and Code Review Rules (§21). Until then, it has no live target in this project.

## Best Practices

- Treat every GitHub action that is visible to others (pushing code, opening/commenting on PRs or issues) as requiring explicit user confirmation — the MCP tools make these actions easy to invoke, which raises rather than lowers the bar for confirming intent first.
- Prefer the MCP tools over shelling out to `gh`, since `gh` is not installed in this environment and the MCP surface is the actual integration point.
- **After registering or approving any MCP server, start a fresh session before assuming its tools are available** — do not spend time debugging "missing tools" in a session that predates the registration.
- **Never run `claude mcp get <server>` (or any command that echoes registered env values) in a way that could be captured in a shared transcript** — see the security note below.

## Limitations

- No live repository connection exists yet — ProjectOne is not currently under git version control locally, so GitHub-side operations (PR creation, issue triage) have no real target to validate end-to-end against today.
- `gh` CLI is unavailable in this environment; any workflow assuming CLI-based GitHub access would fail here.
- No real create/read/update operation against an actual repository has been exercised yet — only credential auth and tool-manifest loading are confirmed.

## Bugs Discovered During Validation

- **Session tool-cache staleness:** newly registered/approved MCP servers do not appear in an already-running session, even though CLI-level status correctly shows them connected. Not a defect in the server itself, but a real operational trap — cost significant back-and-forth before being correctly diagnosed.
- **Env var name mismatch on first attempt:** the official server expects `GITHUB_PERSONAL_ACCESS_TOKEN`; registering with only `GITHUB_PAT` present (without explicit mapping) left the server connected at the process level but unauthenticated for real API calls. Required re-registration with the correct mapping.

## Workarounds

- Always start (or switch to) a new Claude Code session after registering/approving an MCP server before concluding its tools are unavailable.
- Explicitly map any pre-existing token environment variable to the exact name the official server expects — do not assume a differently-named variable (`GITHUB_PAT` vs. `GITHUB_PERSONAL_ACCESS_TOKEN`) will be picked up implicitly.

## Recommendations

- Run a real per-operation validation pass (create a disposable test repository or issue, read it back, clean up) once there is an appropriate target to validate against, and update this note with those concrete results.
- Initialize ProjectOne under git version control before relying on GitHub MCP operations for real work — several tools (branch creation, PR creation, push) presuppose a repository and remote that don't currently exist here.

## Security Note (carried forward from original validation)

During the original installation session, running `claude mcp get github` to inspect the registered configuration **echoed the PAT value in plaintext** into that session's transcript. The token is stored locally in `~/.claude.json` (not committed to any repository — this project isn't under git version control), but any tool-visible transcript of that session contains the live token value. **If that PAT has not already been rotated, treat it as exposed and rotate it now** via GitHub token settings, independent of the separate, more severe credential exposure recorded in [[MCP/Computer Use|Computer Use]].

## Future Improvements

- Replace the "not validated" gap above (real repo/issue/PR operations) with a concrete results table once ProjectOne has a live GitHub remote.
- Document the GitHub Actions / CI integration path (CLAUDE.md §37 Release Philosophy) once ProjectOne has an initial pipeline.

---

## Navigation

- **Previous:** —
- **Next:** [[MCP/Filesystem|Filesystem]]
- **Parent:** [[AI Index]]
- **Related Notes:** [[Chapter 11 - Code Review Standards]] · [[Release Strategy]] · [[MCP/Computer Use|Computer Use]] · [[CLAUDE|CLAUDE.md]]
