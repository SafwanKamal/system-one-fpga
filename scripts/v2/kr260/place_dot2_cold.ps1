$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$build=Join-Path $repoRoot 'build/v2/kr260-opt-dot2'
$status=Get-Content (Join-Path $build 'completion-status.json') -Raw | ConvertFrom-Json
if($status.state -ne 'failed'){throw 'Inspect prior failure before starting cold retry'}
$log=Get-Content (Join-Path $build 'sysone_v2_kr260.runs/impl_1/runme.log') -Raw
if($log -notmatch 'Need spiral search for more than 5% of movable instances'){throw 'Unexpected failure; no automatic retry'}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $build
if($LASTEXITCODE -ne 0){throw 'Synthesis qualification failed'}
$regression=Get-Content (Join-Path $build 'regression.json') -Raw | ConvertFrom-Json
foreach($entry in $regression.rtl_sha256.PSObject.Properties){
    $relative=$entry.Name.Substring('rtl/v2/'.Length)
    $path=Join-Path $build ('rtl-snapshot/'+$relative)
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value){throw 'Frozen regression hash mismatch'}
}
$output=Join-Path $build 'cold-placement'
New-Item -ItemType Directory -Force $output|Out-Null
$checkpoint=Join-Path $build 'sysone_v2_kr260.runs/impl_1/system_wrapper_opt.dcp'
@{checkpoint=$checkpoint;sha256=(Get-FileHash -LiteralPath $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant();reason='Incremental placement could not place remaining cells'}|ConvertTo-Json|Set-Content (Join-Path $output 'source.json')
function Save-Status($state,$detail){@{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json|Set-Content (Join-Path $build 'completion-status.json')}
try{
    Save-Status 'placing_cold' 'Full placement from same optimized checkpoint; failed incremental evidence preserved'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal -log 'S:/build/v2/kr260-opt-dot2/cold-placement/vivado.log' -source 'S:/scripts/v2/kr260/place_dot2_cold.tcl' *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'Cold placement/reporting failed; inspect preserved logs'}
    Save-Status 'cold_placement_ready' 'Cold placed timing/congestion and frequency sweep ready; no routing'
}catch{Save-Status 'cold_failed' $_.Exception.Message;throw}
