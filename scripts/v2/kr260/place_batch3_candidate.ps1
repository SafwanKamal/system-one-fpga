$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch3'
$status = Get-Content (Join-Path $buildDir 'completion-status.json') -Raw | ConvertFrom-Json
if ($status.state -ne 'preflight_ready') { throw 'Passing preflight required; do not duplicate an implementation' }
$regression = Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
foreach ($entry in $regression.rtl_sha256.PSObject.Properties) {
    $relative = $entry.Name.Substring('rtl/v2/'.Length)
    $frozen = Join-Path $buildDir ('rtl-snapshot/' + $relative)
    if ((Get-FileHash -LiteralPath $frozen -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "Frozen RTL differs from regression: $($entry.Name)"
    }
}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if ($LASTEXITCODE -ne 0) { throw 'Fanout/resource qualification failed' }
$reference = Join-Path $repoRoot 'build/v2/kr260-opt-memory/sysone_v2_kr260.runs/impl_1/system_wrapper_routed.dcp'
@{reference=$reference;sha256=(Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash.ToLowerInvariant()} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'incremental-reference.json')
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    Save-Status 'placing' 'Frozen accumulator candidate; stop at placement for congestion review'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-batch3/place-vivado.log' `
        -source 'S:/scripts/v2/kr260/place_batch3_candidate.tcl' *> (Join-Path $buildDir 'place-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Placement/reporting failed; inspect place-console.log before resuming' }
    Save-Status 'placement_ready' 'Placed timing/congestion/reuse reports ready; routing not started'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
