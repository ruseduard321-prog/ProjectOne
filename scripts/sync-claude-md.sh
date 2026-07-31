#!/usr/bin/env bash
#
# Regenerate the repository-root CLAUDE.md from the canonical vault copy.
#
# The canonical, authored source is:
#     ProjectOne Vault/00 Governance/CLAUDE.md
#
# The repository root CLAUDE.md is a generated mirror. Both are needed:
# the Claude Code harness auto-loads only the root file, while every
# [[CLAUDE|CLAUDE.md]] wiki-link in the vault resolves to the vault copy.
# Generating one from the other is what makes drift between them impossible
# (CLAUDE.md §19 — documentation drift is a bug).
#
# What is stripped from the generated copy:
#   - YAML frontmatter    (Obsidian metadata; meaningless to the harness)
#   - the canonical-source callout (it tells vault readers where to edit)
#   - the trailing Navigation block (vault-only wiki-links)
#
# Usage:
#   ./scripts/sync-claude-md.sh          regenerate the root file
#   ./scripts/sync-claude-md.sh --check  verify it is in sync; non-zero if not
#
# --check is the CI/pre-commit form: it never writes, it only reports.
# Idempotent by construction — running it twice produces identical output.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_file="$repo_root/ProjectOne Vault/00 Governance/CLAUDE.md"
target_file="$repo_root/CLAUDE.md"

check_only=false
[[ "${1:-}" == "--check" ]] && check_only=true

if [[ ! -f "$source_file" ]]; then
  echo "error: canonical source not found: $source_file" >&2
  exit 2
fi

# Build the generated content:
#   1. drop YAML frontmatter (everything through the second '---' line)
#   2. drop the "canonical CLAUDE.md" callout block
#   3. drop the trailing "## Navigation" section
generated="$(
  awk '
    NR == 1 && $0 == "---" { in_fm = 1; next }
    in_fm && $0 == "---"   { in_fm = 0; next }
    in_fm                  { next }
    { print }
  ' "$source_file" |
  awk '
    /^> \[!important\] This file is the canonical CLAUDE\.md/ { in_callout = 1; next }
    in_callout && /^>/ { next }
    in_callout && $0 == "" { in_callout = 0; next }
    { print }
  ' |
  awk '
    /^## Navigation$/ { exit }
    { print }
  '
)"

# Trim leading blank lines, then trailing blank lines and any dangling "---"
# separator left behind by removing the Navigation block.
generated="$(printf '%s\n' "$generated" | sed -e '/./,$!d')"
generated="$(printf '%s\n' "$generated" | awk '
  { lines[NR] = $0 }
  END {
    last = NR
    while (last > 0 && (lines[last] == "" || lines[last] == "---")) last--
    for (i = 1; i <= last; i++) print lines[i]
  }
')"

if $check_only; then
  if [[ ! -f "$target_file" ]]; then
    echo "OUT OF SYNC: $target_file does not exist" >&2
    exit 1
  fi
  if diff -q <(printf '%s\n' "$generated") "$target_file" >/dev/null; then
    echo "in sync: CLAUDE.md matches the canonical vault copy"
    exit 0
  fi
  echo "OUT OF SYNC: CLAUDE.md differs from the canonical vault copy." >&2
  echo "The root file is generated — edit '00 Governance/CLAUDE.md' and run:" >&2
  echo "    ./scripts/sync-claude-md.sh" >&2
  exit 1
fi

printf '%s\n' "$generated" > "$target_file"
echo "regenerated: $target_file (from 00 Governance/CLAUDE.md)"
