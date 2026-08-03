---
title: Environment Setup
category: Development
status: stable
version: "1.8"
last_updated: 2026-08-01
tags: [engineering, documentation, ai, mcp]
aliases: ["Local Development Setup", "AI Tooling Setup"]
---

# Environment Setup

The current state of ProjectOne's local development environment and AI operating capabilities, as verified by direct validation rather than assumed from configuration files alone. This note answers "what's actually available and working right now" — for the standards each capability must follow, see [[AI Index]] and the individual [[MCP/GitHub|MCP]] notes.

For how configuration and secrets are handled across environments — the dev/staging/production split, the fail-fast config loading in both apps, and the feature-flag convention — see [[Environment and Secrets]].

## Machine Environment (as validated)

- **OS:** Windows 11, native (not WSL)
- **Shell:** PowerShell (primary, used as the harness's default shell tool since Git for Windows is not installed); Bash also available via the harness's bundled MSYS environment
- **Node.js:** v24.18.0
- **npm:** 11.16.0
- **Git:** available for local operations; `gh` CLI is **not installed** — GitHub operations go through the [[MCP/GitHub|GitHub MCP]], not the CLI
- **Repository state:** ProjectOne **is under git version control** as of STEP-01 — local repository on branch `main`, with a GitHub remote at `github.com/ruseduard321-prog/ProjectOne` added by the project owner on 2026-07-31 (STEP-06). CI runs there on every push and pull request. The `gh` CLI is still **not installed**; GitHub operations go through the [[MCP/GitHub|GitHub MCP]] or plain `git`.
- **Python:** 3.14.6, invoked as `py` on this machine (the Windows launcher). `apps/api` declares `requires-python = ">=3.12"` — 3.14 is what is installed here, not a floor the project imposes.
- **Continuous integration:** GitHub Actions runs `.github/workflows/ci.yml` on every push and pull request as of STEP-06 — a `web` job (lint, type-check, test, build) and an `api` job (lint, format, type-check, test). Both are green. The workflow is the authority on what must pass before a merge; run the same commands locally first. **Confirming a run's result is currently an owner action** — the repository is private and this environment cannot read workflow results (no `gh` CLI, no workflow-run tool in the [[MCP/GitHub|GitHub MCP]]).
- **Web application:** `apps/web` exists as of STEP-03 — Next.js 16.2.12, React 19.2.4, TypeScript strict, Tailwind v4, ESLint 9. Run it with `npm run dev` from `apps/web` (defaults to port 3000). `npm run lint`, `npm run typecheck` and `npm test` (Vitest 4) are the validation entry points. Note that `next lint` was removed in Next.js 16; lint runs through ESLint directly. Requires `.env.local` — it will not build or start without one ([[Environment and Secrets]]).
- **API application:** `apps/api` exists as of STEP-04 — FastAPI 0.121.2, Pydantic 2.12.4, Uvicorn 0.38.0, with Ruff 0.14.5, mypy 1.18.2 and pytest 8.4.2 as dev tooling. Dependencies are pinned exactly in `pyproject.toml` and installed into a local virtual environment at `apps/api/.venv/` (git-ignored). Run it with `.venv/Scripts/python -m uvicorn app.main:app --reload` from `apps/api` (port 8000). Validation entry points: `ruff check .`, `ruff format --check .`, `mypy app`, `pytest`. Interactive API docs are at `/docs`, the OpenAPI contract at `/openapi.json`. Requires `.env` — it will not start without one ([[Environment and Secrets]]).
- **Database:** a development Supabase project (PostgreSQL 17.6) as of STEP-07, reached with `psycopg` 3. Migrations run through Alembic via `./scripts/migrate.sh up` (or `.\scripts\migrate.ps1 up`) — see `scripts/README.md`. `GET /health` reports database connectivity and returns 503 when it is unreachable. Credentials live in `apps/api/.env` and are never committed. **Schema as of STEP-08:** `users`, `workspaces` and `workspace_members` at revision `8a6f39b07c12` — see [[Schema Overview]]. Run `./scripts/migrate.sh up` after pulling to stay current. Row Level Security is **not** enabled yet (STEP-09).

## AI Operating Capabilities — Status Summary

See [[AI Index]] for the full catalog. Summary as of this validation pass:

| Capability | Type | Status |
|---|---|---|
| [[MCP/Filesystem|Filesystem]] | Official MCP server (`@modelcontextprotocol/server-filesystem`) | Configured in `.mcp.json`, fully validated |
| [[MCP/Terminal|Terminal]] | Built-in harness capability | No installation needed, fully validated |
| [[MCP/Playwright|Playwright]] | Harness-native, Playwright-backed | No installation needed, fully validated (Chromium only) |
| [[MCP/Computer Use|Computer Use]] | Built-in harness capability | No installation needed, fully validated against a real native app — **see security incident in the note** |
| [[MCP/GitHub|GitHub]] | Official MCP server | Configured (outside project `.mcp.json`); PAT-authenticated and tool manifest confirmed loadable; no real repository operation exercised yet |
| [[MCP/Supabase|Supabase]] | MCP server (reserved) | Still not installed. A development Supabase project **does** exist as of STEP-07, but the API reaches it over plain PostgreSQL (`psycopg`) and migrations run through Alembic — neither needs the MCP. Install it only if a task genuinely requires dashboard-level operations. |
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

## Obsidian Vault Git Policy

The vault is tracked because it is the product's source of truth. Inside `.obsidian/`, the split is between **configuration the project needs to behave identically on every machine** (tracked) and **per-user state** (ignored):

| File | Tracked? | Why |
|---|---|---|
| `core-plugins.json` | **Tracked** | Which plugins the vault relies on — templates, properties, backlinks, graph. A machine missing these renders the vault differently. |
| `community-plugins.json` | **Tracked** | Same reasoning, for community plugins, if any are adopted later. |
| `app.json` | **Tracked** | Editor behavior (link format, attachment folder) that must not vary per person. |
| `appearance.json` | **Tracked** | Baseline theme/appearance settings shared by the project. |
| `workspace.json`, `workspace-mobile.json`, `workspaces.json` | Ignored | Window layout, open tabs and pane sizes — pure per-machine UI state. Churns on every session and conflicts constantly. |
| `graph.json` | Ignored | Personal graph view: zoom, scale, forces, open/closed state. A view preference, not project configuration. |
| `cache/`, `plugins/*/data.json` | Ignored | Regenerated locally; `data.json` may also hold per-user plugin credentials, which must never be committed ([[CLAUDE\|CLAUDE.md]] §16). |
| `hotkeys.json`, `starred.json` | Ignored | Personal keybindings and bookmarks. |

Two details worth knowing before editing these rules:

- **The patterns are unanchored (`**/.obsidian/...`) deliberately.** There are two `.obsidian/` folders — one at the repository root and one inside `ProjectOne Vault/`. Root-anchored patterns like `.obsidian/workspace.json` silently miss the vault's copy, which is exactly how the vault's `workspace.json` and `graph.json` reached the initial commit and had to be untracked afterwards.
- **Ignoring never untracks.** A file already in the index keeps being committed regardless of `.gitignore`. Removing one requires `git rm --cached`, which drops it from tracking while leaving it on disk.

## Setting Up a New Machine

1. Clone the repository rather than initializing one — `github.com/ruseduard321-prog/ProjectOne` (private).
2. Install Node.js and npm (validated against v24.18.0 / 11.16.0 — the exact versions are not a hard requirement, but this is the last known-good baseline). Then run `npm install` in `apps/web`.
3. Install Python 3.12 or newer (validated against 3.14.6). Create the API's virtual environment and install its pinned dependencies from `apps/api`:

   ```
   py -m venv .venv
   .venv/Scripts/python -m pip install -e ".[dev]"
   ```

   On macOS/Linux the interpreter is `python3` and the venv path is `.venv/bin/python`.
4. Create the local environment files from their committed templates — **both apps refuse to start without them** ([[Environment and Secrets]]):

   ```
   cp apps/api/.env.example apps/api/.env
   cp apps/web/.env.example apps/web/.env.local
   ```

   The web template's defaults are correct as-is. **`apps/api/.env` needs real Supabase credentials** — the API will not start without `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `DATABASE_URL`, `REQUEST_DATABASE_URL` and `PROJECTONE_BYOK_ENCRYPTION_KEY`. Get the first three from the Supabase dashboard (Project Settings → API and → Database); the fourth is set in step 6 below and the fifth in step 7. Neither file is ever committed.
5. Apply migrations so the local database schema matches the code: `./scripts/migrate.sh up` (or `.\scripts\migrate.ps1 up`). Safe to re-run — it is a no-op when already current.
6. **Give the request-path role a password.** Migration `d7b95c1f4e08` creates `projectone_api` — the role the API serves requests as, which unlike `postgres` does not bypass RLS ([[Authentication Implementation]]). The migration deliberately sets no password, because a credential in a migration is a credential in source control. Set one per environment in the Supabase SQL editor:

   ```sql
   ALTER ROLE projectone_api WITH LOGIN PASSWORD '<a strong password>';
   ```

   Then put it in `REQUEST_DATABASE_URL`, using the same host and database as `DATABASE_URL` but with this role and password.

   **This must be repeated after any rollback past `d7b95c1f4e08`** — the downgrade drops the role, so the recreated one has no password and the API fails to connect until it is set again.

   > [!warning] This pairing has no automated consistency check
   > The role's password lives only in the database; `REQUEST_DATABASE_URL` lives only in git-ignored `.env`. Nothing validates that they still agree, so a mismatch is invisible until the first request that touches a tenant table — which cost most of a session on 2026-08-03. [[DOC-02 Validate the Request-Path Credential at Startup]] proposes the fix and is unscheduled.

7. **Generate the BYOK encryption key** (required as of [[STEP-17 AI Router and Provider Abstraction]]). Workspace AI provider keys are encrypted at rest with it, and the API refuses to start without a valid one — the alternative would be storing customer provider keys in plaintext.

   ```bash
   python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"
   ```

   Put the result in `PROJECTONE_BYOK_ENCRYPTION_KEY`. **Per environment, never shared, never committed** ([[CLAUDE|CLAUDE.md]] §28a) — it is a secret in the same class as `DATABASE_URL`.

   **Rotation is not supported yet.** Changing this value makes every stored provider credential undecryptable, and each workspace must re-enter its keys.

8. Ensure `.mcp.json` is present at the project root — the Filesystem server bootstraps automatically via `npx` on first use, no manual install step required.
9. Terminal, Playwright (Chromium), and Computer Use are available immediately with no setup — they ship with the Claude Code harness itself.
10. If GitHub operations are needed, confirm the GitHub MCP server is configured at the appropriate level (user/global config) — this is outside `.mcp.json` and outside this repository's version control.
11. Firefox and WebKit browser binaries are **not** installed by default (Chromium only) — install deliberately with `npx playwright install firefox webkit` only if cross-browser manual validation becomes necessary; this is a real download/disk-write action, not a no-op.

## Known Gaps

- No Supabase or Vercel MCP configuration exists yet. For Vercel this is expected — there is no deployment target. For Supabase a database now exists (STEP-07), but the API reaches it over plain PostgreSQL and migrations run through Alembic, so the MCP is only needed for dashboard-level operations.
- `@playwright/test` is not installed as a project dependency — the harness's Playwright capability is validated for exploratory/manual use only, not automated CI test coverage. See [[MCP/Playwright|Playwright]] Recommendations.
- **GitHub workflow results are not readable from this environment.** Commits push successfully and the [[MCP/GitHub|GitHub MCP]] reads repository data (validated against the real repository as of STEP-06), but the MCP exposes no workflow-run tool, `gh` is not installed, and the repository is private so unauthenticated API and browser access return 404. Confirming a CI run is therefore an owner action. Installing `gh` or adding a workflow-run capability would close this.
- No `08 ADR/` entries exist yet recording these tooling decisions as formally accepted architecture — see [[08 ADR]].

## Unresolved Security Finding

Validating [[MCP/Computer Use|Computer Use]] surfaced two live secrets in plaintext on-screen (a GitHub PAT and an Anthropic API key), captured in a screenshot taken during the validation run. A second, separate incident during [[MCP/GitHub|GitHub]] installation echoed a PAT into a session transcript via `claude mcp get github`. **Rotation status for both is unconfirmed as of 2026-07-31.** Verify and rotate both credentials if this has not already been done — see the Security Incident section in [[MCP/Computer Use|Computer Use]] for full detail.

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[AI Index]] · [[Workflows/Development Workflow|Development Workflow]] · [[MCP/GitHub|GitHub]] · [[MCP/Filesystem|Filesystem]] · [[MCP/Terminal|Terminal]] · [[MCP/Playwright|Playwright]] · [[MCP/Computer Use|Computer Use]]
