$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/dev-env.ps1"
$env:PYTHONPATH = Join-Path (Split-Path -Parent $PSScriptRoot) 'services/worker'
& "$env:PYTHONPATH/.venv/Scripts/python.exe" -m uvicorn caseflow_worker.app:app --host 127.0.0.1 --port 8090
