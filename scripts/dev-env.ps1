$ErrorActionPreference = 'Stop'
$caseflowRoot = Split-Path -Parent $PSScriptRoot
$caseflowEnv = Join-Path $caseflowRoot '.env'
if (-not (Test-Path -LiteralPath $caseflowEnv)) {
    throw 'Run node scripts/init-local.mjs from the repository root first.'
}
foreach ($line in Get-Content -LiteralPath $caseflowEnv) {
    if ($line -match '^(DB_(?:ADMIN|MIGRATOR|API|WORKER)_PASSWORD|S3_ACCESS_KEY|S3_SECRET_KEY)=([a-f0-9]+)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}
if (-not $env:JAVA_HOME) {
    $env:JAVA_HOME = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'Machine')
}
if (-not $env:JAVA_HOME -or -not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin/java.exe'))) {
    throw 'Install JDK 21 and set JAVA_HOME before starting the API.'
}
