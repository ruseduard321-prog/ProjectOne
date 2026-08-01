#!/usr/bin/env bash
#
# Database migration commands for apps/api.
#
# A thin, documented wrapper over Alembic. It exists so that migrating is one
# obvious command rather than tribal knowledge about which directory to stand
# in and which interpreter to use — the venv interpreter is resolved here, so
# an activated shell is not required.
#
# Every schema change is a version-controlled migration file. Manual SQL
# against a live database is forbidden (CLAUDE.md §13).
#
# Usage:
#   ./scripts/migrate.sh up               apply all pending migrations
#   ./scripts/migrate.sh down             roll back exactly one migration
#   ./scripts/migrate.sh status           show current revision and pending work
#   ./scripts/migrate.sh history          show the full migration history
#   ./scripts/migrate.sh new "<message>"  create a new migration file
#   ./scripts/migrate.sh sql              print the SQL for pending migrations
#
# Idempotent: "up" on an up-to-date database is a no-op, and re-running it
# changes nothing. Reads DATABASE_URL from apps/api/.env via the application's
# validated settings — no credential is passed on the command line, where it
# would land in shell history.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_dir="$repo_root/apps/api"

if [[ ! -d "$api_dir" ]]; then
  echo "error: apps/api not found at $api_dir" >&2
  exit 1
fi

# Prefer the project venv so this works without an activated shell. Windows
# (Git Bash) and POSIX venvs put the interpreter in different places.
if [[ -x "$api_dir/.venv/Scripts/python.exe" ]]; then
  python_bin="$api_dir/.venv/Scripts/python.exe"
elif [[ -x "$api_dir/.venv/bin/python" ]]; then
  python_bin="$api_dir/.venv/bin/python"
else
  echo "error: no virtual environment found at apps/api/.venv" >&2
  echo "       create it first — see 09 Development/Environment Setup" >&2
  exit 1
fi

if [[ ! -f "$api_dir/.env" ]]; then
  echo "error: apps/api/.env not found — migrations need DATABASE_URL" >&2
  echo "       copy apps/api/.env.example and fill it in" >&2
  exit 1
fi

command="${1:-}"
cd "$api_dir"

case "$command" in
  up)
    "$python_bin" -m alembic upgrade head
    ;;
  down)
    # Exactly one step, never "base". Rolling the whole schema back is
    # destructive enough that it should be typed out deliberately rather than
    # reachable by a convenience wrapper.
    "$python_bin" -m alembic downgrade -1
    ;;
  status)
    "$python_bin" -m alembic current --verbose
    ;;
  history)
    "$python_bin" -m alembic history --indicate-current
    ;;
  new)
    message="${2:-}"
    if [[ -z "$message" ]]; then
      echo "error: a message is required — ./scripts/migrate.sh new \"add users table\"" >&2
      exit 1
    fi
    "$python_bin" -m alembic revision -m "$message"
    ;;
  sql)
    # Offline mode: renders SQL without touching the database. Review this
    # before applying anything to an environment that matters.
    "$python_bin" -m alembic upgrade head --sql
    ;;
  *)
    echo "usage: ./scripts/migrate.sh {up|down|status|history|new \"<message>\"|sql}" >&2
    exit 1
    ;;
esac
