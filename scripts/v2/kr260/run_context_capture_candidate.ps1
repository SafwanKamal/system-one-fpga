$ErrorActionPreference='Stop'
$repoRoot='C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
$status=Join-Path $repoRoot 'build/v2/attention-context-capture-controller-status.json'
$python=Join-Path $repoRoot '.venv/Scripts/python.exe'
function Save-Status($state,$detail) {
    @{state=$state;detail=$detail;pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $status
}
try {
    $proof=Get-Content (Join-Path $repoRoot 'build/v2/rtl-context-capture-parameter-check/completion-status.json') -Raw | ConvertFrom-Json
    if($proof.complete -ne $true -or $proof.exit_code -ne 0){throw 'Existing complete numerical proof required; never duplicate'}
    Save-Status 'waiting_admission_helpers' 'Numerical run finished; require reviewed gate scripts before freezing/synthesis'
    $receipt=Join-Path $repoRoot 'build/v2/attention-context-capture-gate-scripts-ready.json'
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
    & $python (Join-Path $PSScriptRoot 'freeze_context_capture.py')
    if($LASTEXITCODE -ne 0){throw 'Numerical/default/cycle tradeoff/source admission failed'}
    Save-Status 'synthesizing' 'Frozen attention-context-capture-large at200MHz; routing disabled'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log S:/build/v2/kr260-opt-attention-context-capture-large/preflight-vivado.log `
        -source S:/scripts/v2/kr260/create_project_kr260.tcl `
        -tclargs preflight optimized 200 bram wide memory context-capture large *> (Join-Path $repoRoot 'build/v2/kr260-opt-attention-context-capture-large/preflight-console.log')
    if($LASTEXITCODE -ne 0){throw 'Full synthesis failed; preserve evidence'}
    & $python (Join-Path $PSScriptRoot 'check_batch_preflight.py') (Join-Path $repoRoot 'build/v2/kr260-opt-attention-context-capture-large')
    if($LASTEXITCODE -ne 0){throw 'Inference/resource gates failed; no placement/route'}
    @{state='preflight_ready';target_mhz=200;hardware_deployed=$false;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $repoRoot 'build/v2/kr260-opt-attention-context-capture-large/completion-status.json')
    Save-Status 'preflight_ready' 'Review whole-design timing and resources before placement; no route'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
