# Explicit synthesis-only gate; never queues placement/routing.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch2'
$evidence = Join-Path $repoRoot 'build/v2/rtl-batch2-check'
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) { throw 'Existing batch2 project must be reviewed rather than overwritten' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_batch.py') $evidence
if ($LASTEXITCODE -ne 0) { throw 'Corrected batch regression is incomplete or source changed' }
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Copy-Item (Join-Path $evidence 'summary.json') (Join-Path $buildDir 'regression.json')
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
Save-Status 'synthesizing' 'Build-turnaround gate: corrected query control, fanout, resource fit and UltraRAM registers; routing disabled'
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/kr260-opt-batch2/preflight-vivado.log' `
    -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
    -tclargs preflight optimized 125 bram wide memory batch2 *> (Join-Path $buildDir 'preflight-console.log')
if ($LASTEXITCODE -ne 0) { throw 'Batch2 synthesis gate failed' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if ($LASTEXITCODE -ne 0) { throw 'Inspect resources, URAM inference and query control fanout before routing' }
Save-Status 'preflight_ready' 'Synthesis checks passed; review fanout/timing before any placement or routing'
Write-Host 'Synthesis gates passed. Review reports; no implementation has been launched.'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
