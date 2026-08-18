# Database migration commands for apps/api (Windows PowerShell twin of migrate.sh).
#
# Behavior is identical to the Bash version; both exist so the command is the
# same on every machine, matching the sync-governance-docs.sh/.ps1 pair.
#
# Every schema change is a version-controlled migration file. Manual SQL
# against a live database is forbidden (CLAUDE.md §13).
#
# Usage:
#   .\scripts\migrate.ps1 up               apply all pending migrations
#   .\scripts\migrate.ps1 down             roll back exactly one migration
#   .\scripts\migrate.ps1 status           show current revision
#   .\scripts\migrate.ps1 history          show the full migration history
#   .\scripts\migrate.ps1 new "<message>"  create a new migration file
#   .\scripts\migrate.ps1 sql              print the SQL for pending migrations

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('up', 'down', 'status', 'history', 'new', 'sql')]
    [string]$Command,

    [Parameter(Position = 1)]
    [string]$Message
)

# Alembic logs INFO to stderr. Under Windows PowerShell 5.1 with
# ErrorActionPreference = 'Stop', a native command writing to stderr is turned
# into a terminating NativeCommandError — so ordinary migration output would be
# reported as a failure. 'Continue' lets stderr through as text; real failures
# are still caught, via the exit code checked at the end.
$ErrorActionPreference = 'Continue'

if (-not $Command) {
    Write-Error 'usage: .\scripts\migrate.ps1 {up|down|status|history|new "<message>"|sql}'
    exit 1
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$apiDir = Join-Path $repoRoot 'apps\api'

if (-not (Test-Path $apiDir)) {
    Write-Error "apps/api not found at $apiDir"
    exit 1
}

# Prefer the project venv so this works without an activated shell.
$windowsPython = Join-Path $apiDir '.venv\Scripts\python.exe'
$posixPython = Join-Path $apiDir '.venv/bin/python'

if (Test-Path $windowsPython) {
    $pythonBin = $windowsPython
} elseif (Test-Path $posixPython) {
    $pythonBin = $posixPython
} else {
    Write-Error 'No virtual environment found at apps/api/.venv — create it first (see Environment Setup)'
    exit 1
}

if (-not (Test-Path (Join-Path $apiDir '.env'))) {
    Write-Error 'apps/api/.env not found — migrations need DATABASE_URL. Copy apps/api/.env.example and fill it in.'
    exit 1
}

Push-Location $apiDir
try {
    switch ($Command) {
        'up' { & $pythonBin -m alembic upgrade head }
        # Exactly one step, never "base" — see migrate.sh for the reasoning.
        'down' { & $pythonBin -m alembic downgrade -1 }
        'status' { & $pythonBin -m alembic current --verbose }
        'history' { & $pythonBin -m alembic history --indicate-current }
        'new' {
            if (-not $Message) {
                Write-Error 'A message is required — .\scripts\migrate.ps1 new "add users table"'
                exit 1
            }
            & $pythonBin -m alembic revision -m $Message
        }
        # Offline mode: renders SQL without touching the database.
        'sql' { & $pythonBin -m alembic upgrade head --sql }
    }
    # $LASTEXITCODE is only meaningful when a native command actually ran and
    # set it; a switch branch that produced no external process leaves the
    # previous value in place, which would surface as a bogus failure.
    if ($null -eq $LASTEXITCODE) { exit 0 }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
