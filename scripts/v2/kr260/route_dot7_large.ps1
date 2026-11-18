param([ValidateSet(125,150,200,250,300)][int]$MHz = 150)
$ErrorActionPreference = 'Stop'
if (Get-CimInstance Win32_Process -Filter "Name='vivado.exe'") {
    throw 'One heavy Vivado job at a time; preserve the active job'
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large'
$placed = Get-Content (Join-Path $buildDir placement/completion-status.json) -Raw | ConvertFrom-Json
if ($placed.state -ne 'placement_ready') { throw 'Completed, reviewed placement required' }
$sweep = Get-Content (Join-Path $buildDir placement/frequency-diagnostics.json) -Raw | ConvertFrom-Json
$clock = $sweep | Where-Object { $_.mhz -eq $MHz }
if (-not $clock -or $clock.estimated_setup_slack_ns -lt 0.5) { throw 'Insufficient placement margin for routing this clock' }
$regression = Get-Content (Join-Path $buildDir regression.json) -Raw | ConvertFrom-Json
foreach ($entry in $regression.rtl_sha256.PSObject.Properties) {
    $source = Join-Path (Join-Path $buildDir rtl-snapshot) $entry.Name.Substring('rtl/v2/'.Length)
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw 'Frozen source hash mismatch' }
}
# This receipt is written by the agent after reading timing/congestion, not by placement.
$review = Get-Content (Join-Path $buildDir 'placement/route-review.json') -Raw | ConvertFrom-Json
if ($review.candidate -ne 'dot7-large' -or $review.route_approved -ne $true -or
    $review.selected_mhz -ne $MHz -or [string]::IsNullOrWhiteSpace($review.reason)) {
    throw 'A candidate-specific timing/congestion routing decision is required'
}
foreach ($name in @('system_wrapper_placed.dcp','frequency-diagnostics.json','congestion.rpt')) {
    $expected = $review.placement_sha256.$name
    $actual = (Get-FileHash -LiteralPath (Join-Path $buildDir "placement/$name") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw "Reviewed placement evidence changed: $name" }
}
if ($regression.profile.max_hidden -ne 1024 -or $regression.profile.local_accumulator_controls -ne 3 -or
    $regression.profile.pipelined_dot -ne 1) { throw 'Dot7 H1024 shared-read pipeline profile required' }
$preflight = Get-Content (Join-Path $buildDir 'preflight-summary.json') -Raw | ConvertFrom-Json
if ($preflight.all_uram_outputs_registered -ne $true -or $preflight.lut_reduction_vs_failed_dot5 -lt 5123) {
    throw 'Dot7 synthesis memory/area gates failed'
}
$output = Join-Path $buildDir "route-${MHz}mhz"
if (Test-Path $output) { throw 'Existing routing must be reviewed, never duplicated' }
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status([string]$state,[string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $output completion-status.json)
}
try {
    Save-Status 'routing' 'Frozen placed design; setup/hold required before export or deployment'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log "S:/build/v2/kr260-opt-dot7-large/route-${MHz}mhz/vivado.log" `
        -source 'S:/scripts/v2/kr260/route_dot7_large.tcl' -tclargs $MHz *> (Join-Path $output console.log)
    if ($LASTEXITCODE -ne 0) { throw 'Routing/qualification/export failed; preserve evidence, do not upload' }
    Save-Status 'qualified' 'Routed setup/hold and final export passed; package and hardware tests remain'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
