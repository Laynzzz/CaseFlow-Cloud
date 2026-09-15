$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/dev-env.ps1"
foreach ($line in Get-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) '.env')) {
    if ($line -match '^OPENAI_API_KEY=([^\s]+)$') {
        [Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $Matches[1], 'Process')
    }
}
$env:PYTHONPATH = Join-Path (Split-Path -Parent $PSScriptRoot) 'services/worker'
& "$env:PYTHONPATH/.venv/Scripts/python.exe" -m uvicorn caseflow_worker.app:app --host 127.0.0.1 --port 8090
