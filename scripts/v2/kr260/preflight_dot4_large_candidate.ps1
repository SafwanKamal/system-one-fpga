# Qualify H1024 capacity and attention address cursors with synthesis only; never queue routing.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-dot4-large'
$evidence = Join-Path $repoRoot 'build/v2/rtl-dot4-large-check'
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) { throw 'Existing dot project must be reviewed rather than overwritten' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_batch.py') (Join-Path $repoRoot 'build/v2/rtl-dot4-check') 1 1
if ($LASTEXITCODE -ne 0) { throw 'Base numerical regression/source gate failed' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_large_attention_capacity.py')
if ($LASTEXITCODE -ne 0) { throw 'H1024 numerical regression/source gate failed' }
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Copy-Item (Join-Path $evidence 'summary.json') (Join-Path $buildDir 'regression.json')
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    Save-Status 'synthesizing' 'Deep reduction fanout/resource/inference gate; routing disabled'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-dot4-large/preflight-vivado.log' `
        -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
        -tclargs preflight optimized 300 bram wide memory dot4 large *> (Join-Path $buildDir 'preflight-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Dot4 large synthesis gate failed' }
    & (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
    if ($LASTEXITCODE -ne 0) { throw 'Inspect resource fit, URAM and query/accumulator fanout before routing' }
    Save-Status 'preflight_ready' 'Accumulator/query control fanout gates passed; placement/routing still required'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
