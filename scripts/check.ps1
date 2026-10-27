# One command for every check. Tests run with FAKE_AI=1 and never call a model.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:FAKE_AI = "1"
& "$root\.venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL pytest"; exit 1 }
& node --test "tests/js/*.test.mjs"
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL js tests"; exit 1 }
# Model text and user text must never be inserted as HTML.
$bad = Select-String -Path "$root\static\*.js", "$root\static\*.html" -Pattern 'innerHTML|outerHTML|insertAdjacentHTML|document\.write'
if ($bad) { $bad | ForEach-Object { Write-Host "FAIL html insertion: $($_.Path):$($_.LineNumber)" }; exit 1 }
Write-Host "PASS"
