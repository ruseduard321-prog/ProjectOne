#!/usr/bin/env bash
#
# Regenerate a repository-root CLAUDE.md from a canonical source document.
#
# This script is PROJECT-AGNOSTIC: every path and strip rule comes from
# sync-claude-md.config.json beside it. To adopt it in another project, copy
# this script, sync-claude-md.ps1 and the config file, then edit only the
# config. Nothing below needs to change.
#
# Why two copies of CLAUDE.md exist at all: the Claude Code harness auto-loads
# only the repository-root file, while documentation tools (e.g. an Obsidian
# vault) may need the canonical copy to live elsewhere. Generating one from the
# other makes drift mechanically impossible rather than a rule to remember.
#
# Usage:
#   ./scripts/sync-claude-md.sh          regenerate the target file
#   ./scripts/sync-claude-md.sh --check  verify sync; non-zero exit if not
#
# --check is the CI/pre-commit form: it never writes, it only reports.
# Idempotent by construction — running it twice produces identical output.
#
# The PowerShell twin (sync-claude-md.ps1) implements identical behavior for
# Windows users without a POSIX shell. Both must produce byte-identical output.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
config_file="$script_dir/sync-claude-md.config.json"

if [[ ! -f "$config_file" ]]; then
  echo "error: config not found: $config_file" >&2
  exit 2
fi

# Minimal JSON string/bool reader. Avoids a jq dependency: the config is a flat
# object written by this project, not arbitrary third-party JSON.
read_config_string() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\(.*\)\"[[:space:]]*,\?[[:space:]]*$/\1/p" "$config_file" | head -1
}
read_config_bool() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\(true\|false\).*/\1/p" "$config_file" | head -1
}

source_rel="$(read_config_string source)"
target_rel="$(read_config_string target)"
strip_callout="$(read_config_string stripCalloutStartsWith)"
strip_heading="$(read_config_string stripFromHeading)"
strip_frontmatter="$(read_config_bool stripFrontmatter)"

if [[ -z "$source_rel" || -z "$target_rel" ]]; then
  echo "error: config must define non-empty 'source' and 'target'" >&2
  exit 2
fi

source_file="$repo_root/$source_rel"
target_file="$repo_root/$target_rel"

check_only=false
[[ "${1:-}" == "--check" ]] && check_only=true

if [[ ! -f "$source_file" ]]; then
  echo "error: canonical source not found: $source_file" >&2
  exit 2
fi

generated="$(cat "$source_file")"

# 1. Drop a leading YAML frontmatter block.
if [[ "$strip_frontmatter" == "true" ]]; then
  generated="$(printf '%s\n' "$generated" | awk '
    NR == 1 && $0 == "---" { in_fm = 1; next }
    in_fm && $0 == "---"   { in_fm = 0; next }
    in_fm                  { next }
    { print }
  ')"
fi

# 2. Drop a blockquote callout and its continuation lines.
if [[ -n "$strip_callout" ]]; then
  generated="$(printf '%s\n' "$generated" | awk -v marker="$strip_callout" '
    index($0, marker) == 1 { in_callout = 1; next }
    in_callout && /^>/     { next }
    in_callout && $0 == "" { in_callout = 0; next }
    { print }
  ')"
fi

# 3. Drop a trailing heading and everything after it.
if [[ -n "$strip_heading" ]]; then
  generated="$(printf '%s\n' "$generated" | awk -v heading="$strip_heading" '
    $0 == heading { exit }
    { print }
  ')"
fi

# Trim leading blank lines, then trailing blank lines and any dangling "---"
# separator left behind by removing a trailing section.
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
    echo "OUT OF SYNC: $target_rel does not exist" >&2
    exit 1
  fi
  # Compare ignoring line-ending style: the two scripts run on platforms with
  # different conventions and must agree on content, not on CR bytes.
  if diff -q <(printf '%s\n' "$generated" | tr -d '\r') <(tr -d '\r' < "$target_file") >/dev/null; then
    echo "in sync: $target_rel matches $source_rel"
    exit 0
  fi
  echo "OUT OF SYNC: $target_rel differs from $source_rel." >&2
  echo "The target is generated — edit the source and run:" >&2
  echo "    ./scripts/sync-claude-md.sh" >&2
  exit 1
fi

printf '%s\n' "$generated" > "$target_file"
echo "regenerated: $target_rel (from $source_rel)"
