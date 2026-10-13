# User-space only. Downloads small core assets, never AI model weights or DAWs.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $studioRoot
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv from https://docs.astral.sh/uv/getting-started/installation/ first.' }
    foreach ($path in @('.tools','.downloads','soundfonts','models','outputs','projects')) {
        if (-not (Test-Path -LiteralPath $path)) { New-Item -ItemType Directory -Path $path | Out-Null }
    }
    function Get-VerifiedAsset([string]$Url, [string]$Destination, [string]$Sha256) {
        if (-not (Test-Path -LiteralPath $Destination)) {
            Write-Host "Downloading $Url"
            Invoke-WebRequest -Uri $Url -OutFile $Destination
        }
        $actual = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $Sha256) { throw "Checksum mismatch: $Destination. Existing file retained for inspection." }
    }
    Get-VerifiedAsset 'https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.1/fluidsynth-v2.6.1-win10-x64-cpp11.zip' '.downloads/fluidsynth-2.6.1.zip' 'fab7a2e4b85675b66970f97a39bbc239729c5e0f237198b5922a6a73cbc8677c'
    $fluidDir = '.tools/fluidsynth-2.6.1'
    if (-not (Test-Path -LiteralPath $fluidDir)) {
        Expand-Archive -LiteralPath '.downloads/fluidsynth-2.6.1.zip' -DestinationPath $fluidDir
    }
    Get-VerifiedAsset 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip' '.downloads/ffmpeg.zip' '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
    if (-not (Test-Path -LiteralPath '.tools/ffmpeg')) {
        Expand-Archive -LiteralPath '.downloads/ffmpeg.zip' -DestinationPath '.tools/ffmpeg'
    }
    Get-VerifiedAsset 'https://deb.debian.org/debian/pool/main/t/timgm6mb-soundfont/timgm6mb-soundfont_1.3.orig.tar.gz' '.downloads/timgm.tar.gz' 'af8f3a00e416dfb262bcaa904a1c84df04a51b72bbc1313aed012bc754bdf99b'
    $font = 'soundfonts/TimGM6mb.sf2'
    if (-not (Test-Path -LiteralPath $font)) {
        # Extract one named file only; no executable code from the Debian archive is run.
        & tar -xf '.downloads/timgm.tar.gz' -C soundfonts 'timgm6mb-soundfont_1.3/TimGM6mb.sf2'
        if ($LASTEXITCODE -ne 0) { throw 'SF2 archive extraction failed' }
        Move-Item -LiteralPath 'soundfonts/timgm6mb-soundfont_1.3/TimGM6mb.sf2' -Destination $font
    }
    if ((Get-FileHash -LiteralPath $font -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'c5378b62028c920cb11e4803327983fee2f2cdff5dc89c708e39da417e51c854') { throw 'Installed SF2 differs from expected source; retained without overwriting.' }
    & uv sync --frozen --extra dev --link-mode copy
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    & '.venv/Scripts/music-studio.exe' doctor
    if ($LASTEXITCODE -ne 0) { throw 'Core engine verification failed; inspect outputs/logs.' }
    Write-Host 'Core setup complete. Run .venv/Scripts/python.exe scripts/smoke-test.py for measured audio verification.'
} finally { Pop-Location }
