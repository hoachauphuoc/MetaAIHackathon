# Run the app locally. Default is FAKE_AI=1 (no model calls). -Real uses the Meta key file named
# by META_API_KEY_FILE.
param([switch]$Real, [int]$Port = 5000)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if ($Real) {
    Remove-Item Env:FAKE_AI -ErrorAction SilentlyContinue
    $default = "$HOME\.bjt\MetaAIHackathon.txt"
    if (-not $env:META_API_KEY_FILE -and (Test-Path $default)) { $env:META_API_KEY_FILE = $default }
} else { $env:FAKE_AI = "1" }
& "$root\.venv\Scripts\python.exe" -m flask --app app run --port $Port
