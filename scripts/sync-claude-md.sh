#!/usr/bin/env bash
#
# DEPRECATED COMPATIBILITY SHIM.
#
# CLAUDE.md is no longer the only generated root document — AGENTS.md is
# generated the same way for OpenAI Codex — so the mechanism was renamed to
# sync-governance-docs.sh and now handles both.
#
# This shim exists because the old command name is written into README.md, into
# scripts/README.md, and into the callout at the top of the canonical CLAUDE.md
# itself, and is in the muscle memory of anyone who has worked in this
# repository. Breaking it to save a file would trade a real cost for a cosmetic
# one.
#
# It delegates to the new script restricted to the `claude` document, so its
# behavior is exactly what it always was: this command regenerates CLAUDE.md and
# nothing else.
#
# Prefer ./scripts/sync-governance-docs.sh, which handles every governed
# document. This shim will be removed once the references above have all been
# updated and given time to settle.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "note: sync-claude-md.sh is deprecated — use sync-governance-docs.sh (handles CLAUDE.md and AGENTS.md)" >&2

exec "$script_dir/sync-governance-docs.sh" --only claude "$@"
