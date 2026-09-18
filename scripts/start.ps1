$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Install it, then run this script again.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -c requirements.lock -e '.[dev,analytics]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m aquawatch.cli demo
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
& '.\.venv\Scripts\python.exe' -m aquawatch.cli serve
