param(
    [Parameter(Mandatory=$true)][int]$TrainingPid,
    [Parameter(Mandatory=$true)][string]$ModelName
)
$ErrorActionPreference = 'Stop'
$repoDirectory = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $repoDirectory
if (Get-Process -Id $TrainingPid -ErrorAction SilentlyContinue) {
    Wait-Process -Id $TrainingPid
}
# The Python preparation runner refuses missing/incomplete training results.
& uv run --group train python -u scripts/v2/prepare_kr260_model.py --name $ModelName
if ($LASTEXITCODE -ne 0) {
    throw "Model preparation stopped (exit $LASTEXITCODE); inspect this worker's log."
}
