# Starts an ALREADY provisioned service. No dependency or model download is allowed here.
param(
    [Parameter(Mandatory=$true)][string]$Repository,
    [Parameter(Mandatory=$true)][string]$Checkpoints,
    [ValidateSet('cuda','cpu','xpu')][string]$Device = 'cuda',
    [switch]$EnableLlm
)
$ErrorActionPreference = 'Stop'
$repoPath = (Resolve-Path -LiteralPath $Repository).Path
$weights = (Resolve-Path -LiteralPath $Checkpoints).Path
$python = Join-Path $repoPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Separate ACE-Step environment missing. Follow docs/acestep-3060.md after download approval.' }
foreach ($asset in @('acestep-v15-turbo\model.safetensors','vae\diffusion_pytorch_model.safetensors','Qwen3-Embedding-0.6B\model.safetensors')) {
    if (-not (Test-Path -LiteralPath (Join-Path $weights $asset))) { throw "Missing model file: $asset. This launcher will not download it." }
}
if ($EnableLlm -and -not (Test-Path -LiteralPath (Join-Path $weights 'acestep-5Hz-lm-0.6B\model.safetensors'))) { throw 'Optional 0.6B LM weights missing; launcher will not download them.' }
$variables = @{
    HF_HUB_OFFLINE='1'; TRANSFORMERS_OFFLINE='1'; ACESTEP_CHECKPOINTS_DIR=$weights
    ACESTEP_CONFIG_PATH='acestep-v15-turbo'; ACESTEP_DEVICE=$Device
    ACESTEP_INIT_LLM=([string][bool]$EnableLlm).ToLowerInvariant(); ACESTEP_LM_BACKEND='pt'; ACESTEP_OFFLOAD_TO_CPU='true'
    ACESTEP_LM_MODEL_PATH='acestep-5Hz-lm-0.6B'; ACESTEP_LM_OFFLOAD_TO_CPU='true'
    ACESTEP_API_HOST='127.0.0.1'; ACESTEP_API_PORT='8001'
}
$previous = @{}
foreach ($name in $variables.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
    [Environment]::SetEnvironmentVariable($name,$variables[$name],'Process')
}
Push-Location -LiteralPath $repoPath
try {
    & $python (Join-Path $PSScriptRoot 'acestep_offline_server.py')
    if ($LASTEXITCODE -ne 0) { throw "ACE-Step exited $LASTEXITCODE; inspect service output." }
} finally {
    Pop-Location
    foreach ($name in $variables.Keys) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
}
