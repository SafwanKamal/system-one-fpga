param([ValidateSet(125,150,200)][int]$MHz = 150)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-dot5-large'
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
        -log "S:/build/v2/kr260-opt-dot5-large/route-${MHz}mhz/vivado.log" `
        -source 'S:/scripts/v2/kr260/route_frontier.tcl' -tclargs $MHz *> (Join-Path $output console.log)
    if ($LASTEXITCODE -ne 0) { throw 'Routing/qualification/export failed; preserve evidence, do not upload' }
    Save-Status 'qualified' 'Routed setup/hold and final export passed; package and hardware tests remain'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
