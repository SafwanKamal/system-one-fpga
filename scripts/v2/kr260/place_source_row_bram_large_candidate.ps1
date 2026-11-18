$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado job'}
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir=Join-Path $repoRoot 'build/v2/kr260-opt-source-row-bram-large'
$output=Join-Path $buildDir 'placement'
if(Test-Path $output){throw 'Preserve existing capture placement'}
$status=Get-Content (Join-Path $buildDir 'completion-status.json') -Raw | ConvertFrom-Json
if($status.state -ne 'preflight_ready'){throw 'Review synthesis admission before placement'}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if($LASTEXITCODE -ne 0){throw 'Synthesis resource/pipeline/fanout/capture gate failed'}
$regression=Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
if($regression.numerical_cases -ne 32 -or $regression.read_latency -ne 5 -or $regression.target_mhz -ne 200 -or $regression.profile.registered_fifo_flags -ne 1 -or $regression.profile.probability_pipeline -ne 1 -or $regression.profile.pipelined_drain_select -ne 1 -or @($regression.rtl_sha256.PSObject.Properties).Count -ne 22 -or $regression.profile.probability_input_capture -ne 1 -or $regression.profile.local_embed_controls -ne 1 -or $regression.profile.incremental_source_row -ne 1 -or $regression.profile.linear_accumulators_in_bram -ne 1 -or $regression.capability_word -ne "0x53597fff"){throw 'Wrong numerical profile'}
foreach($property in $regression.rtl_sha256.PSObject.Properties){
    $source=Join-Path (Join-Path $buildDir 'rtl-snapshot') $property.Name.Substring('rtl/v2/'.Length)
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $property.Value){throw "Snapshot mismatch: $($property.Name)"}
}
$review=Get-Content (Join-Path $buildDir 'synthesis-review.json') -Raw | ConvertFrom-Json
if($review.candidate -ne 'source-row-bram-large' -or $review.placement_approved -ne $true -or $review.route_approved -ne $false -or [string]::IsNullOrWhiteSpace($review.reason)){throw 'Candidate-specific synthesis review required'}
foreach($name in @('regression.json','preflight-summary.json','preflight-timing.rpt','preflight-critical.rpt','preflight-fanout.rpt','sysone_v2_kr260.runs/synth_1/system_wrapper.dcp')){
    $actual=(Get-FileHash -LiteralPath (Join-Path $buildDir $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if($actual -ne $review.evidence_sha256.$name){throw "Reviewed synthesis evidence changed: $name"}
}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o');target_mhz=200} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
}
try{
    Save-Status 'placing' 'Frozen capture H1024 at 200 MHz; diagnostic placement, no route'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-source-row-bram-large/placement/vivado.log' `
        -source 'S:/scripts/v2/kr260/place_source_row_bram_large_candidate.tcl' *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'Capture placement failed; preserve reports'}
    Save-Status 'placement_ready' 'Review 200 MHz setup paths, hold, density and congestion before routing'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
