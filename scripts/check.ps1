# One command for every check. Tests run with FAKE_AI=1 and never call a model.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:FAKE_AI = "1"
& "$root\.venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL pytest"; exit 1 }
Write-Host "PASS"
