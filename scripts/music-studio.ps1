# Run without activating a venv or changing system PATH.
$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $studioRoot '.venv\Scripts\music-studio.exe'
if (-not (Test-Path -LiteralPath $cli)) { throw 'Run scripts\bootstrap.ps1 first.' }
$env:MUSIC_STUDIO_HOME = $studioRoot
& $cli @args
exit $LASTEXITCODE
