#!/usr/bin/env bash
#
# Regenerate ProjectOne's repository-root governance documents from their
# canonical vault sources.
#
# This script is PROJECT-AGNOSTIC: every path and strip rule comes from
# sync-governance-docs.config.json beside it. To adopt it in another project,
# copy this script, sync-governance-docs.ps1 and the config file, then edit only
# the config. Nothing below needs to change.
#
# Why two copies of each document exist at all: an agent harness auto-loads only
# the repository-root file (Claude Code reads CLAUDE.md, OpenAI Codex reads
# AGENTS.md), while every wiki-link in the Obsidian vault resolves only to the
# vault copy. Generating one from the other makes drift mechanically impossible
# rather than a rule to remember.
#
# Usage:
#   ./scripts/sync-governance-docs.sh                regenerate every document
#   ./scripts/sync-governance-docs.sh --check        verify all; non-zero if stale
#   ./scripts/sync-governance-docs.sh --only claude  regenerate one document
#
# --check is the CI/pre-commit form: it never writes, it only reports. It checks
# every document and reports all of them before exiting, so one stale file does
# not hide another.
#
# Idempotent by construction — running it twice produces identical output.
#
# The PowerShell twin (sync-governance-docs.ps1) implements identical behavior
# for Windows users without a POSIX shell. Both must produce byte-identical
# output.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
config_file="$script_dir/sync-governance-docs.config.json"

if [[ ! -f "$config_file" ]]; then
  echo "error: config not found: $config_file" >&2
  exit 2
fi

check_only=false
only_name=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) check_only=true; shift ;;
    --only)
      if [[ $# -lt 2 ]]; then
        echo "error: --only requires a document name" >&2
        exit 2
      fi
      only_name="$2"; shift 2 ;;
    *)
      echo "error: unknown argument: $1" >&2
      echo "usage: $(basename "$0") [--check] [--only <name>]" >&2
      exit 2 ;;
  esac
done

# Read one field from the Nth document object. Avoids a jq dependency: the
# config is a flat array of flat objects written by this project, not arbitrary
# third-party JSON. `awk` splits the file into document blocks on the "name"
# key, which every entry must carry, then reads the requested field from the
# selected block.
read_doc_field() {
  local index="$1" key="$2"
  awk -v want="$index" -v key="$key" '
    /"name"[[:space:]]*:/ { block++ }
    block == want {
      pattern = "\"" key "\"[[:space:]]*:[[:space:]]*"
      if (match($0, pattern)) {
        rest = substr($0, RSTART + RLENGTH)
        if (match(rest, /^"[^"]*"/)) {
          value = substr(rest, RSTART + 1, RLENGTH - 2)
          print value
          exit
        }
        if (match(rest, /^(true|false)/)) {
          print substr(rest, RSTART, RLENGTH)
          exit
        }
      }
    }
  ' "$config_file"
}

document_count="$(grep -c '"name"[[:space:]]*:' "$config_file" || true)"

if [[ -z "$document_count" || "$document_count" -eq 0 ]]; then
  echo "error: config defines no documents" >&2
  exit 2
fi

# Render one document to stdout, applying the configured strip rules.
render_document() {
  local source_file="$1" strip_frontmatter="$2" strip_callout="$3" strip_heading="$4"
  local generated
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
  printf '%s\n' "$generated" | awk '
    { lines[NR] = $0 }
    END {
      last = NR
      while (last > 0 && (lines[last] == "" || lines[last] == "---")) last--
      for (i = 1; i <= last; i++) print lines[i]
    }
  '
}

matched=false
stale=false

for (( i = 1; i <= document_count; i++ )); do
  name="$(read_doc_field "$i" name)"
  source_rel="$(read_doc_field "$i" source)"
  target_rel="$(read_doc_field "$i" target)"
  strip_frontmatter="$(read_doc_field "$i" stripFrontmatter)"
  strip_callout="$(read_doc_field "$i" stripCalloutStartsWith)"
  strip_heading="$(read_doc_field "$i" stripFromHeading)"

  if [[ -n "$only_name" && "$name" != "$only_name" ]]; then
    continue
  fi
  matched=true

  if [[ -z "$source_rel" || -z "$target_rel" ]]; then
    echo "error: document '$name' must define non-empty 'source' and 'target'" >&2
    exit 2
  fi

  source_file="$repo_root/$source_rel"
  target_file="$repo_root/$target_rel"

  if [[ ! -f "$source_file" ]]; then
    echo "error: canonical source not found: $source_file" >&2
    exit 2
  fi

  generated="$(render_document "$source_file" "$strip_frontmatter" "$strip_callout" "$strip_heading")"

  if $check_only; then
    if [[ ! -f "$target_file" ]]; then
      echo "OUT OF SYNC: $target_rel does not exist" >&2
      stale=true
      continue
    fi
    # Compare ignoring line-ending style: the two scripts run on platforms with
    # different conventions and must agree on content, not on CR bytes.
    if diff -q <(printf '%s\n' "$generated" | tr -d '\r') <(tr -d '\r' < "$target_file") >/dev/null; then
      echo "in sync: $target_rel matches $source_rel"
    else
      echo "OUT OF SYNC: $target_rel differs from $source_rel." >&2
      stale=true
    fi
    continue
  fi

  printf '%s\n' "$generated" > "$target_file"
  echo "regenerated: $target_rel (from $source_rel)"
done

if [[ -n "$only_name" ]] && ! $matched; then
  echo "error: no document named '$only_name' in the config" >&2
  exit 2
fi

if $stale; then
  echo "The targets above are generated — edit the source and run:" >&2
  echo "    ./scripts/sync-governance-docs.sh" >&2
  exit 1
fi
