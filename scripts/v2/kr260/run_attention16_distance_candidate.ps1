$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$status=Join-Path $repoRoot 'build/v2/attention16-distance-controller-status.json'
$python=Join-Path $repoRoot '.venv/Scripts/python.exe'
function Save-Status($state,$detail) {
    @{state=$state;detail=$detail;pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $status
}
try {
    Save-Status 'regressing' 'Fresh parameterized16querylane/fabricdistance full numerical/default/partial/head32 proof; preserve22sources'
    & wsl.exe -d Ubuntu-24.04 --cd $repoRoot -- env PATH=/opt/verilator-5.040/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash simulation/v2/run_kr260_attention16_distance_parameter.sh
    if($LASTEXITCODE -ne 0){throw 'Parameterized regression failed'}
    Save-Status 'waiting_admission_helpers' 'Numerical run finished; require reviewed gate scripts before freezing/synthesis'
    $receipt=Join-Path $repoRoot 'build/v2/attention16-distance-gate-scripts-ready.json'
    $wait=[Diagnostics.Stopwatch]::StartNew()
    while(!(Test-Path $receipt)){
        if($wait.Elapsed.TotalHours -gt 3){throw 'Admission helper timeout; no full build launched'}
        Start-Sleep -Seconds 15
    }
    $ready=Get-Content $receipt -Raw | ConvertFrom-Json
    if($ready.ready -ne $true){throw 'Admission helpers not qualified'}
    foreach($entry in $ready.sha256.PSObject.Properties){
        if((Get-FileHash -LiteralPath (Join-Path $repoRoot $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value){throw 'Admission helper changed after review'}
    }
    if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado job'}
    & $python (Join-Path $PSScriptRoot 'freeze_attention16_distance.py')
    if($LASTEXITCODE -ne 0){throw 'Numerical/default/cycle tradeoff/source admission failed'}
    Save-Status 'synthesizing' 'Frozen attention16-distance-large at200MHz; routing disabled'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log S:/build/v2/kr260-opt-attention16-distance-large/preflight-vivado.log `
        -source S:/scripts/v2/kr260/create_project_kr260.tcl `
        -tclargs preflight optimized 200 bram wide memory attention16-distance large *> (Join-Path $repoRoot 'build/v2/kr260-opt-attention16-distance-large/preflight-console.log')
    if($LASTEXITCODE -ne 0){throw 'Full synthesis failed; preserve evidence'}
    & $python (Join-Path $PSScriptRoot 'check_batch_preflight.py') (Join-Path $repoRoot 'build/v2/kr260-opt-attention16-distance-large')
    if($LASTEXITCODE -ne 0){throw 'Inference/resource gates failed; no placement/route'}
    @{state='preflight_ready';target_mhz=200;hardware_deployed=$false;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $repoRoot 'build/v2/kr260-opt-attention16-distance-large/completion-status.json')
    Save-Status 'preflight_ready' 'Review whole-design timing and resources before placement; no route'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
