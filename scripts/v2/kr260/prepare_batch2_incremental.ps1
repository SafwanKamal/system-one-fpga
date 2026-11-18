$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch2'
# Re-evaluate gate reports; do not trust a stale completion marker alone.
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if ($LASTEXITCODE -ne 0) { throw 'Fanout/resource gates must pass before preparing reuse' }
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/kr260-opt-batch2/incremental-prepare-vivado.log' `
    -source 'S:/scripts/v2/kr260/prepare_batch2_incremental.tcl' *> (Join-Path $buildDir 'incremental-prepare-console.log')
if ($LASTEXITCODE -ne 0) { throw 'Incremental preparation failed; do not route' }
$reference = Join-Path $repoRoot 'build/v2/kr260-opt-memory/sysone_v2_kr260.runs/impl_1/system_wrapper_routed.dcp'
@{reference=$reference;sha256=(Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash.ToLowerInvariant();implementation_started=$false} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'incremental-reference.json')
