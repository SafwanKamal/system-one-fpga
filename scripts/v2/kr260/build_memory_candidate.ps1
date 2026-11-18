$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-memory'
$vivadoExe = 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat'
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) {
    throw 'Memory project already exists; inspect it before rebuilding'
}
if (!(Test-Path 'S:/scripts/v2/kr260/create_project_kr260.tcl')) {
    throw 'The short S: repository mapping is required'
}
# Refuse launching against changed or incomplete simulation evidence.
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_memory.py')
if ($LASTEXITCODE -ne 0) { throw 'Memory regression qualification failed' }
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot 'build/v2/rtl-memory-check/summary.json') -Destination (Join-Path $buildDir 'regression.json')
function Save-Status([string]$state, [string]$detail) {
    @{state=$state; detail=$detail; updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    Save-Status 'building' 'Pipelined UltraRAM candidate: isolated 125 MHz implementation'
    & $vivadoExe -mode batch -nojournal -log 'S:/build/v2/kr260-opt-memory/build-vivado.log' `
        -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
        -tclargs build optimized 125 bram wide memory *> (Join-Path $buildDir 'build-console.log')
    if ($LASTEXITCODE -ne 0 -and !(Test-Path (Join-Path $buildDir 'sysone_v2_kr260.runs/impl_1/system_wrapper.bit'))) {
        throw 'Memory implementation failed; inspect build-console.log'
    }
    Save-Status 'checking' 'Measuring routed setup/hold and final memory allocation'
    & $vivadoExe -mode batch -nojournal -log 'S:/build/v2/kr260-opt-memory/clock-candidates-vivado.log' `
        -source 'S:/scripts/v2/kr260/report_clock_candidates.tcl' `
        -tclargs memory *> (Join-Path $buildDir 'clock-candidates-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Memory clock qualification failed' }
    Save-Status 'reports_ready' 'Routed resource/clock reports ready; deployment packaging still required'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
