$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch'
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) {
    throw 'Batch project already exists; inspect its preflight before rebuilding'
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    & (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_batch.py')
    if ($LASTEXITCODE -ne 0) { throw 'Batch regression evidence incomplete or changed' }
    Copy-Item -LiteralPath (Join-Path $repoRoot 'build/v2/rtl-batch-check/summary.json') -Destination (Join-Path $buildDir 'regression.json')
    Save-Status 'waiting_memory' 'Regression passed; waiting for the memory candidate to finish before synthesis preflight'
    $deadline = [DateTime]::UtcNow.AddHours(8)
    do {
        $memoryState = Get-Content -LiteralPath (Join-Path $repoRoot 'build/v2/kr260-opt-memory/completion-status.json') -Raw | ConvertFrom-Json
        if ($memoryState.state -eq 'failed') { throw "Memory candidate failed: $($memoryState.detail)" }
        if ($memoryState.state -eq 'reports_ready') { break }
        if ([DateTime]::UtcNow -gt $deadline) { throw 'Memory candidate wait timed out; inspect its logs' }
        Start-Sleep -Seconds 30
    } while ($true)
    # Check again immediately before freezing sources for synthesis.
    & (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_batch.py')
    if ($LASTEXITCODE -ne 0) { throw 'Batch source/evidence changed while waiting' }
    Save-Status 'synthesizing' 'Synthesis-only preflight: resource fit and UltraRAM output registers'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-batch/preflight-vivado.log' `
        -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
        -tclargs preflight optimized 125 bram wide memory batch *> (Join-Path $buildDir 'preflight-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Batch synthesis preflight failed; inspect preflight-console.log' }
    & (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'scripts/v2/kr260/check_batch_preflight.py')
    if ($LASTEXITCODE -ne 0) { throw 'Batch resource or UltraRAM output-register preflight needs review' }
    Save-Status 'preflight_ready' 'Resource and UltraRAM register reports ready for review before full routing'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
