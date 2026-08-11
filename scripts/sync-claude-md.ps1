<#
.SYNOPSIS
    DEPRECATED compatibility shim — use sync-governance-docs.ps1.

.DESCRIPTION
    CLAUDE.md is no longer the only generated root document — AGENTS.md is
    generated the same way for OpenAI Codex — so the mechanism was renamed to
    sync-governance-docs.ps1 and now handles both.

    This shim exists because the old command name is written into README.md,
    into scripts/README.md, and into the callout at the top of the canonical
    CLAUDE.md itself. Breaking it to save a file would trade a real cost for a
    cosmetic one.

    It delegates to the new script restricted to the `claude` document, so its
    behavior is exactly what it always was: this command regenerates CLAUDE.md
    and nothing else.

.PARAMETER Check
    Verify CLAUDE.md is in sync without writing. Exits non-zero if it is not.
#>

[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$target    = Join-Path $scriptDir 'sync-governance-docs.ps1'

Write-Warning "sync-claude-md.ps1 is deprecated - use sync-governance-docs.ps1 (handles CLAUDE.md and AGENTS.md)"

if ($Check) {
    & $target -Check -Only claude
} else {
    & $target -Only claude
}

exit $LASTEXITCODE
