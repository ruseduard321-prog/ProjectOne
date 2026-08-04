---
title: Environment Setup
category: Development
status: stable
version: "1.9"
last_updated: 2026-08-05
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

   The web template's defaults are correct as-is. **`apps/api/.env` needs real Supabase credentials** — the API will not start without `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `DATABASE_URL`, `REQUEST_DATABASE_URL` and `PROJECTONE_BYOK_ENCRYPTION_KEY`. Get the first three from the Supabase dashboard (Project Settings → API and → Database); the fourth is generated in step 6 below and the fifth in step 7. Neither file is ever committed.

   > [!important] Use the **Session pooler** connection string, not the direct one
   > Both `DATABASE_URL` and `REQUEST_DATABASE_URL` point at `aws-0-<region>.pooler.supabase.com:5432` — see [[#The Connection Architecture]] below for why, and for the two details that are easy to get wrong.

5. Apply migrations so the local database schema matches the code: `./scripts/migrate.sh up` (or `.\scripts\migrate.ps1 up`). Safe to re-run — it is a no-op when already current.
6. **Generate the request-path role's credential.** Migration `d7b95c1f4e08` creates `projectone_api` — the role the API serves requests as, which unlike `postgres` does not bypass RLS ([[Authentication Implementation]]). The migration deliberately sets no password, because a credential in a migration is a credential in source control.

   **Do not set it by hand.** Run:

   ```bash
   python scripts/sync-request-role-credential.py
   ```

   It generates the password, applies it with `ALTER ROLE`, **proves it by connecting as that role** and asserting `rolbypassrls = false`, and only then rewrites `REQUEST_DATABASE_URL`. No human ever sees or types the value, so it cannot reach a terminal history, a clipboard or a transcript.

   To check the two still agree without changing anything:

   ```bash
   python scripts/sync-request-role-credential.py --check
   ```

   **Re-run the script after any rollback past `d7b95c1f4e08`** — the downgrade drops the role, so the recreated one has no password.

   > [!warning] Why this is a script rather than a documented SQL statement
   > The role's password lives only in the database; `REQUEST_DATABASE_URL` lives only in git-ignored `.env`. **Two independent writes with nothing linking them**, so a divergence is invisible until the first request that touches a tenant table. That is not hypothetical: it happened twice on 2026-08-03 and cost most of two sessions, the second time after a manual `ALTER ROLE` that was believed to have fixed it. Automating the pair is the fix; [[DOC-02 Validate the Request-Path Credential at Startup]] proposes catching it at boot as well.

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

## The Connection Architecture

**Both connection strings use the Supabase Session pooler on port 5432.** Established 2026-08-03 by owner decision and verified end-to-end; this is now the documented architecture, not a workaround.

```
DATABASE_URL          postgres.<project-ref>@aws-0-<region>.pooler.supabase.com:5432
REQUEST_DATABASE_URL  projectone_api.<project-ref>@aws-0-<region>.pooler.supabase.com:5432
```

### Why not the direct connection

`db.<project-ref>.supabase.co` publishes **an AAAA record and no A record** — Supabase serves direct connections over IPv6 only, with IPv4 available as a paid add-on. Verified against three independent resolvers. An IPv4-only network therefore cannot reach it at all: `getaddrinfo` returns an address with no route and the connection fails before authentication is attempted.

The session pooler is IPv4-reachable on every tier, and reaches the database over IPv6 on Supabase's side.

### Three details that are mandatory

1. **Username is `<role>.<project-ref>`.** A bare `projectone_api` is rejected by the pooler. Verified: both forms were tested, only the qualified one connects.
2. **Port 5432 (session mode), never 6543 (transaction mode).** Transaction mode does not support prepared statements, which psycopg uses.
3. **The region must be correct.** Every `aws-0-<region>.pooler.supabase.com` hostname resolves, so DNS cannot tell you which is yours — a wrong region fails with `password authentication failed`, indistinguishable from a wrong credential. Take it from the dashboard, or prove it by connecting.

### What was verified

The pooler was not assumed to preserve the properties multi-tenancy depends on — each was checked over it:

| Property | Result |
|---|---|
| `projectone_api` authenticates | ✅ |
| `rolbypassrls = false` | ✅ — policies apply |
| `rolinherit = false` | ✅ — a missing `SET ROLE` fails closed |
| `SET LOCAL ROLE` + transaction-scoped `set_config` | ✅ |
| Cross-tenant read of `provider_credentials` | ✅ **blocked** |
| Cross-tenant update | ✅ **blocked** (0 rows) |
| `DELETE` | ✅ **refused** |
| Negative control (RLS disabled → breach observed, then restored) | ✅ |

> [!note] The application code was already pooler-safe, by accident of an earlier decision
> `RequestSessionFactory` uses `SET LOCAL ROLE` and transaction-scoped `set_config` because [[STEP-10 Authentication Backend]] found that session-scoped forms leak a caller's identity into the next request on a pooled connection. That choice — made for a different reason — is exactly what transaction-mode pooling requires, so the tenant isolation model transferred to the pooler unchanged.

## Running the database-backed tests locally

**Roughly half the API suite only executes with a real PostgreSQL, and the development Supabase project cannot host it** — the session pooler requires a `<role>.<project-ref>` username, while `conftest.request_database_url` rebuilds the DSN with a bare `projectone_api`. Without a local server those tests *skip*, and a skip reads as a pass: STEP-19 pushed three database-only defects to CI that no offline run could have caught, because 192 tests silently never ran.

A throwaway local server closes that gap and needs no installer or admin rights. The EnterpriseDB downloads return 403 from this machine; the PostgreSQL 17 binaries published to Maven Central work:

```bash
curl -o pg.jar https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/17.4.0/embedded-postgres-binaries-windows-amd64-17.4.0.jar
```

Unzip it, extract the inner `postgres-windows-x86_64.txz`, then `initdb -D data -U postgres --auth=md5 --pwfile=...` and start on a port that does not collide with anything else (5433 was used).

Then run the suite exactly as CI does — the environment variables are the whole point, since `PROJECTONE_REQUIRE_DATABASE_TESTS` is what turns a silent skip into a failure:

```bash
PROJECTONE_TEST_DATABASE_URL=postgresql://postgres:...@127.0.0.1:5433/projectone_test PROJECTONE_REQUIRE_DATABASE_TESTS=1 pytest -ra
```

**`DATABASE_URL` and `REQUEST_DATABASE_URL` must stay distinct**, as they are in production and in the CI workflow. Collapsing them onto the unprivileged role is what caused STEP-19's `permission denied for table ai_budgets`: the privileged path lost rights that the `ai_budgets` column grant is only meant to deny the tenant connection.

Expected result: **518 passed, 0 skipped**. Any skip means the database was not reached.

## Known Gaps

- No Supabase or Vercel MCP configuration exists yet. For Vercel this is expected — there is no deployment target. For Supabase a database now exists (STEP-07), but the API reaches it over plain PostgreSQL and migrations run through Alembic, so the MCP is only needed for dashboard-level operations.
- `@playwright/test` is not installed as a project dependency — the harness's Playwright capability is validated for exploratory/manual use only, not automated CI test coverage. See [[MCP/Playwright|Playwright]] Recommendations.
- **GitHub workflow results are not readable from this environment.** Commits push successfully and the [[MCP/GitHub|GitHub MCP]] reads repository data (validated against the real repository as of STEP-06), but the MCP exposes no workflow-run tool, `gh` is not installed, and the repository is private so unauthenticated API and browser access return 404. Confirming a CI run is therefore an owner action. Installing `gh` or adding a workflow-run capability would close this.
	- **Mitigated since STEP-19**, though not closed: the full CI suite now runs locally against a real PostgreSQL (see above), so a red run is reproducible here rather than diagnosable only from the owner's screen. The workflow also writes pytest output to the run's step summary and an artifact, both readable without admin rights — which is what made STEP-19's three failures actionable.
- No `08 ADR/` entries exist yet recording these tooling decisions as formally accepted architecture — see [[08 ADR]].

## Unresolved Security Finding

Validating [[MCP/Computer Use|Computer Use]] surfaced two live secrets in plaintext on-screen (a GitHub PAT and an Anthropic API key), captured in a screenshot taken during the validation run. A second, separate incident during [[MCP/GitHub|GitHub]] installation echoed a PAT into a session transcript via `claude mcp get github`. **Rotation status for both is unconfirmed as of 2026-07-31.** Verify and rotate both credentials if this has not already been done — see the Security Incident section in [[MCP/Computer Use|Computer Use]] for full detail.

---

## Navigation

- **Previous:** —
- **Next:** —
- **Parent:** [[Development MOC]]
- **Related Notes:** [[AI Index]] · [[Workflows/Development Workflow|Development Workflow]] · [[MCP/GitHub|GitHub]] · [[MCP/Filesystem|Filesystem]] · [[MCP/Terminal|Terminal]] · [[MCP/Playwright|Playwright]] · [[MCP/Computer Use|Computer Use]]
