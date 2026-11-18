param([ValidateSet(200)][int]$MHz = 200)
$ErrorActionPreference = 'Stop'
if (Get-CimInstance Win32_Process -Filter "Name='vivado.exe'") {
    throw 'One heavy Vivado job at a time; preserve the active job'
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-request-window-embed-large'
$placed = Get-Content (Join-Path $buildDir placement/completion-status.json) -Raw | ConvertFrom-Json
if ($placed.state -ne 'placement_ready') { throw 'Completed, reviewed placement required' }
$sweep = Get-Content (Join-Path $buildDir placement/frequency-diagnostics.json) -Raw | ConvertFrom-Json
$clock = $sweep | Where-Object { $_.mhz -eq $MHz }
if (-not $clock -or $clock.estimated_setup_slack_ns -lt 0.5) { throw 'Insufficient placement margin for routing this clock' }
$regression = Get-Content (Join-Path $buildDir regression.json) -Raw | ConvertFrom-Json
if ($regression.query_group_cases -ne 4 -or $regression.partial_tile_cases -ne 6 -or $regression.profile.attention_lanes -ne 16 -or $regression.profile.fabric_score_distance -ne 1 -or $regression.capability_word -ne '0x5363ffff') { throw 'Exact 16-query fabric-distance numerical profile required' }
if ($regression.profile.cached_request_window -ne 1 -or $regression.profile.dsp_embed_row_address -ne 1) { throw 'Both new window/DSP address stages required' }
foreach ($entry in $regression.rtl_sha256.PSObject.Properties) {
    $source = Join-Path (Join-Path $buildDir rtl-snapshot) $entry.Name.Substring('rtl/v2/'.Length)
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw 'Frozen source hash mismatch' }
}
# This receipt is written by the agent after reading timing/congestion, not by placement.
$review = Get-Content (Join-Path $buildDir 'placement/route-review.json') -Raw | ConvertFrom-Json
if ($review.candidate -ne 'request-window-embed-large' -or $review.route_approved -ne $true -or
    $review.selected_mhz -ne $MHz -or [string]::IsNullOrWhiteSpace($review.reason)) {
    throw 'A candidate-specific timing/congestion routing decision is required'
}
foreach ($name in @('system_wrapper_placed.dcp','frequency-diagnostics.json','congestion.rpt')) {
    $expected = $review.placement_sha256.$name
    $actual = (Get-FileHash -LiteralPath (Join-Path $buildDir "placement/$name") -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) { throw "Reviewed placement evidence changed: $name" }
}
if ($regression.profile.max_hidden -ne 1024 -or $regression.profile.local_accumulator_controls -ne 3 -or
    $regression.profile.pipelined_dot -ne 1 -or $regression.profile.local_read_capture -ne 1 -or
    $regression.read_latency -ne 5 -or $regression.profile.registered_fifo_flags -ne 1 -or $regression.profile.probability_pipeline -ne 1 -or $regression.profile.pipelined_drain_select -ne 1 -or $regression.profile.probability_input_capture -ne 1 -or $regression.profile.local_embed_controls -ne 1 -or $regression.profile.incremental_source_row -ne 1 -or $regression.profile.linear_accumulators_in_bram -ne 1 -or $regression.capability_word -ne '0x5363ffff' -or @($regression.rtl_sha256.PSObject.Properties).Count -ne 23) { throw 'Capture H1024 shared-read pipeline profile required' }
$preflight = Get-Content (Join-Path $buildDir 'preflight-summary.json') -Raw | ConvertFrom-Json
if ($preflight.linear_block_bank_primitives -le 0 -or $preflight.incremental_source_row.row_registers -le 0 -or $preflight.incremental_source_row.linear_lutram_cells -ne 0) { throw 'LINEAR bank/row inference required' }
if ($preflight.operand_capture.probability_input_registered_dsps -ne 16 -or $preflight.operand_capture.local_embed_control_ff -le 0 -or $preflight.pipeline_cuts.registered_probability_dsps -ne 16 -or $preflight.pipeline_cuts.drain_bank_capture_ff -lt 256 -or $preflight.length_fifo_flag_registers -ne 2 -or $preflight.local_read_capture_registers -ne 896 -or $preflight.all_uram_outputs_registered -ne $true -or $preflight.lut_reduction_vs_failed_dot5 -lt 5123) {
    throw 'Capture synthesis memory/area gates failed'
}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if ($LASTEXITCODE -ne 0) { throw 'Candidate-specific inference/area gates failed' }
if ($preflight.attention_width_distance.query_lanes -ne 16 -or $preflight.attention_width_distance.external_distance_ff -ne 352 -or $preflight.attention_width_distance.distance_dsp_mapping_passed -ne 16 -or $preflight.query_control_registers -ne 512 -or $preflight.accumulator_original_control_registers -ne 512) { throw '16-query distance/control inventory required' }
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
        -log "S:/build/v2/kr260-opt-request-window-embed-large/route-${MHz}mhz/vivado.log" `
        -source 'S:/scripts/v2/kr260/route_request_window_embed_large.tcl' -tclargs $MHz *> (Join-Path $output console.log)
    if ($LASTEXITCODE -ne 0) { throw 'Routing/qualification/export failed; preserve evidence, do not upload' }
    Save-Status 'qualified' 'Routed setup/hold and final export passed; package and hardware tests remain'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
