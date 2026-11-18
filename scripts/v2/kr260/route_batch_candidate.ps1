$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch'
$status = Get-Content (Join-Path $buildDir 'completion-status.json') -Raw | ConvertFrom-Json
if ($status.state -ne 'preflight_ready') { throw 'Passing preflight required; do not duplicate an active implementation' }
$regression = Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
foreach ($entry in $regression.rtl_sha256.PSObject.Properties) {
    $relative = $entry.Name.Substring('rtl/v2/'.Length)
    $frozen = Join-Path $buildDir ('rtl-snapshot/' + $relative)
    if ((Get-FileHash -LiteralPath $frozen -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Frozen RTL differs from regression: $($entry.Name)"
    }
}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py')
if ($LASTEXITCODE -ne 0) { throw 'Preflight qualification failed' }
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    Save-Status 'building' 'Routing frozen grouped batch at 125 MHz from completed synthesis'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-batch/route-vivado.log' `
        -source 'S:/scripts/v2/kr260/route_batch_candidate.tcl' *> (Join-Path $buildDir 'route-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Batch implementation failed; inspect route-console.log' }
    Save-Status 'checking' 'Measuring routed clock candidates and resources'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-batch/clock-candidates-vivado.log' `
        -source 'S:/scripts/v2/kr260/report_clock_candidates.tcl' -tclargs batch *> (Join-Path $buildDir 'clock-candidates-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Batch clock qualification failed' }
    Save-Status 'reports_ready' 'Routed timing/resources ready; review clock margin before packaging or deployment'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
