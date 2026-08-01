# scripts/

Automation scripts. Deterministic and idempotent where practical, per
[Chapter 02 - Repository Architecture](../ProjectOne%20Vault/04%20Engineering%20Handbook/Chapter%2002%20-%20Repository%20Architecture.md)
§2.7.

## Database migrations

| File | Purpose |
|---|---|
| `migrate.sh` | macOS / Linux / Git Bash |
| `migrate.ps1` | Windows PowerShell (5.1 and 7+) |

A thin wrapper over [Alembic](https://alembic.sqlalchemy.org/), so migrating is one obvious command
rather than tribal knowledge about which directory to stand in and which interpreter to use. Both
resolve the `apps/api/.venv` interpreter themselves, so no activated shell is required.

**Every schema change is a version-controlled migration file. Manual SQL against a live database is
forbidden** ([CLAUDE.md](../CLAUDE.md) §13).

| Command | Effect |
|---|---|
| `up` | Apply all pending migrations. A no-op when already current. |
| `down` | Roll back **exactly one** migration. |
| `status` | Current revision. |
| `history` | Full migration history, current revision marked. |
| `new "<message>"` | Create a new migration file. |
| `sql` | Print the SQL for pending migrations without touching the database. |

```bash
./scripts/migrate.sh up
```

```powershell
.\scripts\migrate.ps1 up
```

Credentials come from `apps/api/.env` through the application's validated settings — never from the
command line, where they would land in shell history. Both scripts fail with a clear message when
that file or the virtual environment is missing.

### Notes

- **`down` rolls back one step, never to `base`.** Dropping an entire schema should be typed out
  deliberately, not reachable through a convenience wrapper.
- **Review before applying to anything that matters.** `sql` renders a migration offline so it can be
  read before it runs.
- `migrate.ps1` sets `$ErrorActionPreference = 'Continue'` because Alembic logs progress to stderr,
  which Windows PowerShell 5.1 would otherwise turn into a terminating error on a successful run.
  Real failures are still caught — via the exit code.

## CLAUDE.md synchronization

| File | Purpose |
|---|---|
| `sync-claude-md.sh` | macOS / Linux / Git Bash |
| `sync-claude-md.ps1` | Windows PowerShell (5.1 and 7+) |
| `sync-claude-md.config.json` | All paths and strip rules — the only file a project edits |

Two copies of CLAUDE.md exist because they serve different consumers: the Claude Code harness
auto-loads **only** the repository-root `CLAUDE.md`, while every `[[CLAUDE|CLAUDE.md]]` wiki-link in
the Obsidian vault resolves **only** to the vault copy. Deleting either breaks a real consumer.

Generating one from the other is what makes drift impossible — it is a mechanism, not a rule someone
has to remember. `ProjectOne Vault/00 Governance/CLAUDE.md` is the canonical authored source; the
root file is generated output and must never be hand-edited.

### Usage

Regenerate the root file after editing the canonical source:

```bash
./scripts/sync-claude-md.sh
```

```powershell
.\scripts\sync-claude-md.ps1
```

Verify sync without writing (CI / pre-commit form — exits non-zero when stale):

```bash
./scripts/sync-claude-md.sh --check
```

```powershell
.\scripts\sync-claude-md.ps1 -Check
```

Both implementations read the same config and produce **byte-identical output** (LF endings, UTF-8
without BOM), so a repository can be maintained from either platform without churn. `--check`
compares content and ignores line-ending style, so a CRLF checkout on Windows does not report false
drift.

### Adopting this in another project

The synchronization logic contains no project-specific paths. Copy the three files into
`scripts/`, then edit **only** `sync-claude-md.config.json`:

| Key | Meaning |
|---|---|
| `source` | Canonical authored file, relative to the repository root. Forward slashes on every platform. |
| `target` | Generated file, relative to the repository root. |
| `stripFrontmatter` | Remove a leading YAML `---` block from the generated copy. |
| `stripCalloutStartsWith` | Drop a blockquote callout starting with this text, plus its continuation lines. Empty string disables. |
| `stripFromHeading` | Drop this heading and everything after it. Empty string disables. |

Nothing in either script needs to change — the scripts are the mechanism, the config is the project.

### Notes

- The Bash script parses the flat config with `sed` rather than requiring `jq`, so it has no
  dependency beyond a POSIX shell and `awk`.
- The PowerShell script targets Windows PowerShell 5.1, so it avoids `??`, ternaries and
  `ConvertFrom-Json -AsHashtable`.
- Both scripts exit `2` on a configuration or missing-source error, and `1` when `--check` finds
  drift — distinguishable in CI.
