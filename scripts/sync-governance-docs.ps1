<#
.SYNOPSIS
    Regenerate ProjectOne's repository-root governance documents from their
    canonical vault sources.

.DESCRIPTION
    Windows/PowerShell twin of sync-governance-docs.sh. Both read the same
    sync-governance-docs.config.json and must produce byte-identical output, so
    a project can be maintained from either platform.

    This script is PROJECT-AGNOSTIC: every path and strip rule comes from the
    config file beside it. To adopt it in another project, copy both scripts
    and the config, then edit only the config.

    Compatible with Windows PowerShell 5.1 and PowerShell 7+.

.PARAMETER Check
    Verify the targets are in sync without writing. Exits non-zero if any is
    not. This is the CI / pre-commit form. Every document is checked and
    reported before exiting, so one stale file does not hide another.

.PARAMETER Only
    Process just the named document from the config instead of all of them.

.EXAMPLE
    .\scripts\sync-governance-docs.ps1
    Regenerate every governed document.

.EXAMPLE
    .\scripts\sync-governance-docs.ps1 -Check
    Verify sync; non-zero exit if any target is stale.

.EXAMPLE
    .\scripts\sync-governance-docs.ps1 -Only claude
    Regenerate only the CLAUDE.md mirror.
#>

[CmdletBinding()]
param(
    [switch]$Check,
    [string]$Only
)

$ErrorActionPreference = 'Stop'

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot   = Split-Path -Parent $scriptDir
$configFile = Join-Path $scriptDir 'sync-governance-docs.config.json'

if (-not (Test-Path $configFile)) {
    Write-Error "config not found: $configFile"
    exit 2
}

$config = Get-Content -Path $configFile -Raw -Encoding UTF8 | ConvertFrom-Json

$documents = $config.documents

if ($null -eq $documents -or @($documents).Count -eq 0) {
    Write-Error "config defines no documents"
    exit 2
}

# Apply the configured strip rules to one source file, returning the generated
# content with LF endings and a single trailing newline.
function Convert-Document {
    param(
        [string]$SourceFile,
        [object]$Document
    )

    # Read as lines, ignoring the source file's line-ending style.
    $lines = (Get-Content -Path $SourceFile -Raw -Encoding UTF8) -split "`r?`n"

    # 1. Drop a leading YAML frontmatter block.
    if ($Document.stripFrontmatter) {
        if ($lines.Count -gt 0 -and $lines[0] -eq '---') {
            $end = -1
            for ($i = 1; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -eq '---') { $end = $i; break }
            }
            if ($end -ge 0) {
                if ($end + 1 -le $lines.Count - 1) {
                    $lines = $lines[($end + 1)..($lines.Count - 1)]
                } else {
                    $lines = @()
                }
            }
        }
    }

    # 2. Drop a blockquote callout and its continuation lines.
    $calloutMarker = $Document.stripCalloutStartsWith
    if (-not [string]::IsNullOrEmpty($calloutMarker)) {
        $kept = New-Object System.Collections.Generic.List[string]
        $inCallout = $false
        foreach ($line in $lines) {
            if (-not $inCallout -and $line.StartsWith($calloutMarker)) { $inCallout = $true; continue }
            if ($inCallout) {
                if ($line.StartsWith('>')) { continue }
                if ($line -eq '') { $inCallout = $false; continue }
            }
            $kept.Add($line)
        }
        $lines = $kept.ToArray()
    }

    # 3. Drop a trailing heading and everything after it.
    $stopHeading = $Document.stripFromHeading
    if (-not [string]::IsNullOrEmpty($stopHeading)) {
        $kept = New-Object System.Collections.Generic.List[string]
        foreach ($line in $lines) {
            if ($line -eq $stopHeading) { break }
            $kept.Add($line)
        }
        $lines = $kept.ToArray()
    }

    # Trim leading blank lines.
    $start = 0
    while ($start -lt $lines.Count -and $lines[$start] -eq '') { $start++ }

    # Trim trailing blank lines and any dangling '---' separator left behind.
    $last = $lines.Count - 1
    while ($last -ge $start -and ($lines[$last] -eq '' -or $lines[$last] -eq '---')) { $last-- }

    if ($last -ge $start) {
        $generated = $lines[$start..$last]
    } else {
        $generated = @()
    }

    # Join with LF and a single trailing newline, matching the Bash twin exactly.
    return (($generated -join "`n") + "`n")
}

$matched = $false
$stale   = $false

foreach ($document in $documents) {
    if (-not [string]::IsNullOrEmpty($Only) -and $document.name -ne $Only) {
        continue
    }
    $matched = $true

    $sourceRel = $document.source
    $targetRel = $document.target

    if ([string]::IsNullOrWhiteSpace($sourceRel) -or [string]::IsNullOrWhiteSpace($targetRel)) {
        Write-Error "document '$($document.name)' must define non-empty 'source' and 'target'"
        exit 2
    }

    # Config paths use forward slashes on every platform; normalize for Windows.
    $sourceFile = Join-Path $repoRoot ($sourceRel -replace '/', [IO.Path]::DirectorySeparatorChar)
    $targetFile = Join-Path $repoRoot ($targetRel -replace '/', [IO.Path]::DirectorySeparatorChar)

    if (-not (Test-Path $sourceFile)) {
        Write-Error "canonical source not found: $sourceFile"
        exit 2
    }

    $content = Convert-Document -SourceFile $sourceFile -Document $document

    if ($Check) {
        if (-not (Test-Path $targetFile)) {
            Write-Host "OUT OF SYNC: $targetRel does not exist" -ForegroundColor Red
            $stale = $true
            continue
        }
        $existing = Get-Content -Path $targetFile -Raw -Encoding UTF8
        # Compare ignoring line-ending style: the two scripts run on platforms
        # with different conventions and must agree on content, not on CR bytes.
        $normalizedExisting  = $existing -replace "`r`n", "`n"
        $normalizedGenerated = $content  -replace "`r`n", "`n"
        if ($normalizedExisting -eq $normalizedGenerated) {
            Write-Host "in sync: $targetRel matches $sourceRel"
        } else {
            Write-Host "OUT OF SYNC: $targetRel differs from $sourceRel." -ForegroundColor Red
            $stale = $true
        }
        continue
    }

    # Write UTF-8 without BOM and with LF endings, so both scripts agree byte for byte.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($targetFile, $content, $utf8NoBom)
    Write-Host "regenerated: $targetRel (from $sourceRel)"
}

if (-not [string]::IsNullOrEmpty($Only) -and -not $matched) {
    Write-Error "no document named '$Only' in the config"
    exit 2
}

if ($stale) {
    Write-Host "The targets above are generated - edit the source and run:"
    Write-Host "    .\scripts\sync-governance-docs.ps1"
    exit 1
}
