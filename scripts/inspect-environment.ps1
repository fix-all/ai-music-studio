param([string]$Output)
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$commands = @{}
foreach ($name in @('python','py','uv','git','ffmpeg','ffprobe','node','nvidia-smi','nvcc','rocminfo','fluidsynth')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { $commands[$name] = $cmd.Source } else { $commands[$name] = $null }
}
$versions = @{}
foreach ($name in @('python','uv','git','node')) {
    if ($commands[$name]) { $versions[$name] = ((& $commands[$name] --version 2>&1) | Out-String).Trim() }
}
$software = @(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
    Where-Object {$_.DisplayName -match 'Ardour|MuseScore|REAPER|Ableton|FL Studio|Cubase|Cakewalk|LMMS|Studio One|Bitwig|Audacity|CUDA|ROCm|FluidSynth|sfizz'} |
    Select-Object DisplayName,DisplayVersion,InstallLocation)
$studioRoot = Split-Path -Parent $PSScriptRoot
$scanRoots = @('C:\Program Files\Common Files\VST3','C:\Program Files\Common Files\VST2',
    (Join-Path $env:USERPROFILE 'Music'), (Join-Path $env:USERPROFILE 'Downloads'),
    (Join-Path $env:USERPROFILE '.cache\huggingface\hub'), 'E:\models','E:\AI', (Split-Path -Parent $studioRoot))
$found = @()
foreach ($scanRoot in $scanRoots) {
    if (Test-Path -LiteralPath $scanRoot) {
        if (Get-Command rg -ErrorAction SilentlyContinue) {
            $found += @(rg --files --hidden -g '*.sf2' -g '*.sfz' -g '*.vst3' -g '*ace*step*' -g '!node_modules' -g '!.git' -g '!.venv*' -g '!venv*' -g '!docs/evidence' $scanRoot 2>$null)
        }
        if ($scanRoot -match 'VST') { $found += @(Get-ChildItem -LiteralPath $scanRoot -Directory -Filter '*.vst3' | ForEach-Object FullName) }
    }
}
$modelDirs = @()
$hub = Join-Path $env:USERPROFILE '.cache\huggingface\hub'
if (Test-Path -LiteralPath $hub) { $modelDirs = @(Get-ChildItem -LiteralPath $hub -Directory -Filter 'models--*' | ForEach-Object Name) }
$data = [ordered]@{
    inspected_at = [DateTimeOffset]::UtcNow.ToString('o')
    os = @{caption=$os.Caption; version=$os.Version; build=$os.BuildNumber; architecture=$os.OSArchitecture; memory_bytes=[int64]$os.TotalVisibleMemorySize*1024}
    cpu = @(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
    gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion)
    gpu_memory_note = 'WMI AdapterRAM and device-name memory are not a verified dedicated VRAM budget; no XPU runtime installed by this project.'
    disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace)
    commands=$commands; versions=$versions; installed_audio_software=$software
    scan_roots=$scanRoots; discovered_assets=@($found | Sort-Object -Unique); huggingface_model_directories=$modelDirs
    scan_limit = 'Known locations only; unlisted custom directories and portable tools may exist.'
}
if ($commands['nvidia-smi']) {
    $data['nvidia_smi'] = ((& $commands['nvidia-smi'] --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1) | Out-String).Trim()
}
$json = $data | ConvertTo-Json -Depth 8
if ($Output) {
    if (Test-Path -LiteralPath $Output) { throw "Refusing to overwrite environment report: $Output" }
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($Output), $json, [Text.UTF8Encoding]::new($false))
} else { $json }
exit 0
